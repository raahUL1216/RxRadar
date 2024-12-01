import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, File, UploadFile
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.web import SpiderWebReader

from server.utils.embedding import MedWebPageReader, store_documents

UPLOAD_DIR = Path('./server/data')
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter(
    prefix='/knowledge',
    tags=['Knowledge']
)

# spider_reader = SpiderWebReader(
#     api_key=os.getenv('SPIDER_API_KEY'),
#     mode='crawl',
#     # params={} # Optional parameters see more on https://spider.cloud/docs/api
# )


@router.post('/upload')
def upload_files(files: List[UploadFile] = File(...)):
    saved_files = []
    for file in files:
        file_path = UPLOAD_DIR / file.filename
        with file_path.open('wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(str(file_path))

    documents = SimpleDirectoryReader(
        input_dir='server/data',
        required_exts=['.pdf', '.md']
    ).load_data(show_progress=True)

    store_documents(documents)

    return {'message': 'Files uploaded successfully.', 'files': saved_files}


@router.post('/upload_webpages')
def parse_webpages(urls: List[str]):
    documents = MedWebPageReader(
        html_to_text=True
    ).load_data(urls=urls)
   
    print(f'parsed documents from {urls} successfully. total documents: {len(documents)}')

    store_documents(documents)

    return {'message': 'Webpages uploaded successfully.', 'urls': urls}
