# Hosting

Create a Streamlit Community Cloud app from this repository. Set entry point `app.py`, branch `main` and Python 3.12. The platform installs `requirements.txt` and FFmpeg through `packages.txt`. No application secret or paid API is needed.

Official instructions: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

For a Python host, install Python requirements and FFmpeg, then run `python start_server.py`. This reads the host's `PORT` (default 8501). Docker hosting is also configured; the host must provide HTTPS and WebSocket forwarding. The health endpoint is `/_stcore/health`.

After deployment, verify both the generated example and a PNG/MP3 upload through Embed, ZIP download, ZIP upload in Decode, image download and audio playback. Public hosting and concurrent-user behavior must be checked on the actual host.
