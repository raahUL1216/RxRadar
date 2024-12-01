import random
from typing import List

from llama_index.core.tools import BaseTool
from llama_index.core.workflow import Context
from pydantic import BaseModel

from server.utils.embedding import get_answer, get_med_index
from server.utils.workflow import (
    AgentConfig,
    ProgressEvent,
)
from server.utils.misc import FunctionToolWithContext


def get_initial_state() -> dict:
    return {
        "username": None,
        "session_token": None,
        "user_address": None,
        "account_id": None,
        "account_balance": None,
    }


class Prescription(BaseModel):
    medicines: List[str] = []


def get_medicine_tools() -> list[BaseTool]:
    def lookup_generic_info(ctx: Context, query: str) -> str:
        """Useful for finding generic info about a company/product."""
        ctx.write_event_to_stream(
            ProgressEvent(msg=f"Looking up")
        )
        
        answer = get_answer(query)

        print((query, answer))

        return answer
    
    def lookup_medicine_info(ctx: Context, medicine_name: str) -> str:
        """Useful for looking up a product or medicine info."""
        ctx.write_event_to_stream(
            ProgressEvent(msg=f"Looking up info for {medicine_name}")
        )

        answer = get_answer(f'Briefly explain the medicine: {medicine_name}. If there is no reference of {medicine_name}, response with NA.')

        print((medicine_name, answer))

        return f"{medicine_name}: {answer}"

    def compare_medicine_prices(ctx: Context, medicine_name: str) -> str:
        """Useful for comparing medicine prices across platforms."""
        ctx.write_event_to_stream(
            ProgressEvent(
                msg=f"Looking up medicine prices for {medicine_name}")
        )

        # todo: API to get medicine prices from all platforms
        prices = {
            "Amazon": 10.99,
            "Walmart": 9.99,
            "Target": 8.99
        }

        price_str = f"Price for {medicine_name} are:\n"
        for platform, price in prices.items():
            price_str += f" {platform}: {price}\n"

        return price_str

    def is_prescription_valid(ctx: Context, prescription: Prescription) -> bool:
        """Useful for validating prescription."""
        ctx.write_event_to_stream(
            ProgressEvent(msg=f"Validating prescription")
        )

        if not len(prescription.get('medicines')):
            raise ValueError("Prescription is not valid!")

        return True

    def is_user_eligible_for_copay_assistance(ctx: Context) -> bool:
        """Useful for checking if user is eligible for copay assistance."""
        ctx.write_event_to_stream(
            ProgressEvent(
                msg="Checking if user is eligible for copay assistance"
            )
        )

        return random.random() > 0.5

    async def buy_medicines(ctx: Context, prescription: Prescription) -> str:
        """Useful for buying a prescibed medicine."""
        ctx.write_event_to_stream(
            ProgressEvent(msg="Buying prescibed medicine")
        )

        valid = is_prescription_valid(ctx, prescription)

        if not valid:
            raise ValueError("Prescription is not valid!")

        user_state = await ctx.get("user_state")
        user_address = user_state['user_address']

        # check if user is eligible for copay/patient assistance programs
        copay_available = is_user_eligible_for_copay_assistance(ctx)

        if copay_available:
            # 5$% discount when user is eligible for copay assitant program
            user_state['account_balance'] = user_state['account_balance'] - (prescription.get('price', 0) - 5)
        else:
            user_state['account_balance'] = user_state['account_balance'] - prescription.get('price', 0)

        await ctx.set("user_state", user_state)

        message = f'Your order is placed and will be delivered to {user_address}.'
        copay_availed_msg = "Congrats! you also availed 5$ discount under our copay assistance program."

        return message + ' ' + copay_availed_msg if copay_available else message

    return [
        FunctionToolWithContext.from_defaults(fn=lookup_medicine_info),
        FunctionToolWithContext.from_defaults(fn=compare_medicine_prices),
        FunctionToolWithContext.from_defaults(fn=is_prescription_valid),
        FunctionToolWithContext.from_defaults(async_fn=buy_medicines),
    ]


def get_patient_support_tools() -> list[BaseTool]:
    async def find_doctor(ctx: Context, address: str) -> str:
        """Useful for finding a doctor for a medicine."""
        user_state = await ctx.get("user_state")
        user_address = user_state['user_address']

        ctx.write_event_to_stream(
            ProgressEvent(msg=f"Finding a doctor near {user_address}...")
        )
        
        # todo: find nearby doctors
        return f"Dr. Smith is a doctor near {user_address}."

    return [
        FunctionToolWithContext.from_defaults(async_fn=find_doctor),
    ]

def get_stock_lookup_tools() -> list[BaseTool]:
    def lookup_stock_price(ctx: Context, stock_symbol: str) -> str:
        """Useful for looking up a stock price."""
        ctx.write_event_to_stream(
            ProgressEvent(msg=f"Looking up stock price for {stock_symbol}")
        )
        return f"Symbol {stock_symbol} is currently trading at $100.00"

    def search_for_stock_symbol(ctx: Context, company_name: str) -> str:
        """Useful for searching for a stock symbol given a free-form company name."""
        ctx.write_event_to_stream(ProgressEvent(msg="Searching for stock symbol"))
        return company_name.upper()

    return [
        FunctionToolWithContext.from_defaults(fn=lookup_stock_price),
        FunctionToolWithContext.from_defaults(fn=search_for_stock_symbol),
    ]


def get_authentication_tools() -> list[BaseTool]:
    async def is_authenticated(ctx: Context) -> bool:
        """Checks if the user has a session token."""
        ctx.write_event_to_stream(ProgressEvent(msg="Checking if authenticated"))
        user_state = await ctx.get("user_state")
        return user_state["session_token"] is not None

    async def store_username(ctx: Context, username: str) -> None:
        """Adds the username to the user state."""
        ctx.write_event_to_stream(ProgressEvent(msg="Recording username"))
        user_state = await ctx.get("user_state")
        user_state["username"] = username
        await ctx.set("user_state", user_state)

    async def store_user_address(ctx: Context, user_address: str) -> None:
        """Adds the user_address to the user state."""
        ctx.write_event_to_stream(ProgressEvent(msg="Recording user_address"))
        user_state = await ctx.get("user_state")
        user_state["user_address"] = user_address
        await ctx.set("user_state", user_state)

    async def login(ctx: Context, password: str) -> str:
        """Given a password, logs in and stores a session token in the user state."""
        user_state = await ctx.get("user_state")
        username = user_state["username"]
        ctx.write_event_to_stream(ProgressEvent(msg=f"Logging in user {username}"))
        # todo: actually check the password
        session_token = "1234567890"
        user_state["session_token"] = session_token
        user_state["account_id"] = "123"
        user_state["account_balance"] = 100

        await ctx.set("user_state", user_state)

        return f"Logged in user {username} with session token {session_token}. They have an account with id {user_state['account_id']} and a balance of ${user_state['account_balance']}."

    return [
        FunctionToolWithContext.from_defaults(async_fn=store_username),
        FunctionToolWithContext.from_defaults(async_fn=store_user_address),
        FunctionToolWithContext.from_defaults(async_fn=login),
        FunctionToolWithContext.from_defaults(async_fn=is_authenticated),
    ]


def get_account_balance_tools() -> list[BaseTool]:
    async def is_authenticated(ctx: Context) -> bool:
        """Checks if the user has a session token."""
        ctx.write_event_to_stream(ProgressEvent(msg="Checking if authenticated"))
        user_state = await ctx.get("user_state")
        return user_state["session_token"] is not None

    async def get_account_id(ctx: Context, account_name: str) -> str:
        """Useful for looking up an account ID."""
        is_auth = await is_authenticated(ctx)
        if not is_auth:
            raise ValueError("User is not authenticated!")

        ctx.write_event_to_stream(
            ProgressEvent(msg=f"Looking up account ID for {account_name}")
        )
        user_state = await ctx.get("user_state")
        account_id = user_state["account_id"]

        return f"Account id is {account_id}"

    async def get_account_balance(ctx: Context, account_id: str) -> str:
        """Useful for looking up an account balance."""
        is_auth = await is_authenticated(ctx)
        if not is_auth:
            raise ValueError("User is not authenticated!")

        ctx.write_event_to_stream(
            ProgressEvent(msg=f"Looking up account balance for {account_id}")
        )
        user_state = await ctx.get("user_state")
        account_balance = user_state["account_balance"]

        return f"Account {account_id} has a balance of ${account_balance}"

    return [
        FunctionToolWithContext.from_defaults(async_fn=get_account_id),
        FunctionToolWithContext.from_defaults(async_fn=get_account_balance),
        FunctionToolWithContext.from_defaults(async_fn=is_authenticated),
    ]


def get_agent_configs() -> list[AgentConfig]:
    return [
        AgentConfig(
            name="Medicine Sales Agent",
            description="Helps with medicine lookup, medicine price comparison, buying medicines etc.",
            system_prompt="""
You are a helpful assistant specialized in assisting users with medicine-related inquiries and transactions. You can:

1. Answer questions about company/product.
2. Look up detailed information about a medicine by name.
3. Compare medicine prices across different platforms to find the best deals.
4. Assist with purchasing medicines if the user provides a valid prescription and account information.

Guidelines:
- For general questions, use the `lookup_generic_info` tool.
- For medicine lookup, only use the `lookup_medicine_info` tool and do not add extenal information, even if it appears unusual.
- For comparing prices, provide a detailed price comparison using the `compare_medicine_prices` tool.
- For buying medicines, perform below steps in strict order:
  1) Ensure the user provides a username, password, and delivery address.
  2) Use the `login` tool to authenticate the user first and then only check for valid prescription
  3) Confirm the order and provide the user with delivery details.
            """,
            tools=get_medicine_tools(),
        ),
        AgentConfig(
            name="Patient Support Agent",
            description="Helps with patient support - find nearby doctors.",
            system_prompt="""
You are a helpful assistant that is helping patient to find nearby doctors.
To do this, the user must supply you with a username, a valid password and user_address. You can ask them to supply these. If the user supplies a username, password and user_address, call the tool "login" to log them in.
Once the user is logged in and authenticated, you can transfer them to another agent.
            """,
            tools=get_patient_support_tools(),
        ),
        AgentConfig(
            name="Authentication Agent",
            description="Handles user authentication",
            system_prompt="""
You are a helpful assistant that is authenticating a user.
Your task is to get a valid session token stored in the user state.
To do this, the user must supply you with a username and a valid password. You can ask them to supply these.
If the user supplies a username and password, call the tool "login" to log them in.
Once the user is logged in and authenticated, you can transfer them to another agent.
            """,
            tools=get_authentication_tools(),
        ),
        AgentConfig(
            name="Account Balance Agent",
            description="Checks account balances",
            system_prompt="""
You are a helpful assistant that is looking up account balances.
The user may not know the account ID of the account they're interested in,
so you can help them look it up by the name of the account.
The user can only do this if they are authenticated, which you can check with the is_authenticated tool.
If they aren't authenticated, tell them to authenticate first and call the "RequestTransfer" tool.
If they're trying to transfer money, they have to check their account balance first, which you can help with.
            """,
            tools=get_account_balance_tools(),
        )
    ]
