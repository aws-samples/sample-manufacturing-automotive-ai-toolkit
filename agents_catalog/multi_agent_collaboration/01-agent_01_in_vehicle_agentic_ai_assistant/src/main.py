import uvicorn
from agent import app

def main():
    """
    Run the VISTA Agent server using uvicorn.
    """
    print("Starting VISTA Agent server...")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info", access_log=False)

if __name__ == "__main__":
    main()
