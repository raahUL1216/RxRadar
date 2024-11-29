import os
import json
from fastapi import APIRouter
from fastapi import WebSocket, WebSocketDisconnect
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.openai import OpenAI

from server.utils.agent_config import get_agent_configs, get_initial_state
from server.utils.embedding import get_med_index, save_chat
from server.utils.workflow import ConciergeAgent, ProgressEvent, ToolApprovedEvent, ToolRequestEvent

from colorama import Fore, Style
    
router = APIRouter(
	prefix='/agent',
	tags=['Agent']
)


@router.get('/query')
def ask_agent(query: str):
	index = get_med_index()

	query_engine = index.as_query_engine()
	response = query_engine.query(query)

	return {'question': query, 'answer': response.response}

def load_chat():
    """Load memory from file."""
    if os.path.exists('server/memory.json'):
        with open('server/memory.json', 'r') as f:
            return ChatMemoryBuffer.from_dict(json.load(f))
    return ChatMemoryBuffer.from_defaults(llm=llm)


# Initialize shared configurations
llm = OpenAI(model="gpt-4o", temperature=0.4)
memory = load_chat()
initial_state = get_initial_state()
agent_configs = get_agent_configs()


workflow = ConciergeAgent(timeout=None)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # send chat history
        chat_history = memory.model_dump()['chat_store']['store'].get('chat_history') or []
        conversation = [{'role': message['role'], 'message': message['content']} for message in chat_history if message['role'] in ["user", "assistant"] and message['content'] is not None]
        
        if conversation:
            await websocket.send_json({'conversation': conversation})  
        
        # Welcome message
        await websocket.send_text(f"Hi there! How can I help you today?")

        user_msg = await websocket.receive_text()
        handler = workflow.run(
            user_msg=user_msg,
            agent_configs=agent_configs,
            llm=llm,
            chat_history=memory.get(),
            initial_state=initial_state,
        )

        while True:
            async for event in handler.stream_events():
                if isinstance(event, ToolRequestEvent):
                    await websocket.send_text(
                        f"Are you sure you want to proceed? Please respond with 'y' or 'n'"
                    )
                    print(
                        Fore.GREEN
                        + "SYSTEM >> I need approval for the following tool call:"
                        + Style.RESET_ALL
                    )
                    print(event.tool_name)
                    print(event.tool_kwargs)
                    print()
                
                    # Wait for user's approval via WebSocket
                    approval = await websocket.receive_text()
                    if "y" in approval.lower() or "yes" in approval.lower():
                        handler.ctx.send_event(
                            ToolApprovedEvent(
                                tool_id=event.tool_id,
                                tool_name=event.tool_name,
                                tool_kwargs=event.tool_kwargs,
                                approved=True,
                            )
                        )
                    else:
                        print(Fore.GREEN + f"SYSTEM >> {event.msg}" + Style.RESET_ALL) 
                        await websocket.send_text(f"Why not? Please provide a reason: ")
                        reason = await websocket.receive_text()
                        handler.ctx.send_event(
                            ToolApprovedEvent(
                                tool_name=event.tool_name,
                                tool_id=event.tool_id,
                                tool_kwargs=event.tool_kwargs,
                                approved=False,
                                response=reason,
                            )
                        )
                elif isinstance(event, ProgressEvent):
                    print(Fore.GREEN + f"SYSTEM >> {event.msg}" + Style.RESET_ALL)

            # Await final result and send to the client
            result = await handler
            print(Fore.BLUE + f"AGENT >> {result['response']}" + Style.RESET_ALL)
            await websocket.send_text(f"{result['response']}")

            # Update memory with only new chat history
            for i, msg in enumerate(result["chat_history"]):
                if i >= len(memory.get()):
                    memory.put(msg)

            # Wait for the user's next message
            user_msg = await websocket.receive_text()
            if user_msg.strip().lower() in ["exit", "quit", "bye"]:
                await websocket.send_text(f"Fare the well!")
                break

            # Pass in the existing context and continue the conversation
            handler = workflow.run(
                ctx=handler.ctx,
                user_msg=user_msg,
                agent_configs=agent_configs,
                llm=llm,
                chat_history=memory.get(),
                initial_state=initial_state,
            )
    except WebSocketDisconnect:
        print("SYSTEM >> Client disconnected.")
        save_chat(memory)
