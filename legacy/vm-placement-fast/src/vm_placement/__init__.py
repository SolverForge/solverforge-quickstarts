import uvicorn

from .rest_api import app as app


def main():
    config = uvicorn.Config("vm_placement:app",
                            port=7860,
                            log_level="info",
                            use_colors=True)
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
