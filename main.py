import multiprocessing
import uvicorn


def run_backend():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )


def run_webdrive():
    uvicorn.run(
        "webdrive.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False
    )


if __name__ == "__main__":
    backend_process = multiprocessing.Process(target=run_backend)
    webdrive_process = multiprocessing.Process(target=run_webdrive)

    backend_process.start()
    webdrive_process.start()

    backend_process.join()
    webdrive_process.join()