# How to run ThumbsUp Frontend in Docker

1. Build the Docker image:
   docker build -t thumbs-up-frontend .

2. Run the container with port forwarding (8080 is the default):
   docker run -p 8080:8080 thumbs-up-frontend

3. To access from another device on your network:
   - Find your host machine's IP address (e.g., 192.168.1.100)
   - Visit http://192.168.1.100:8080 from another device

4. Certificates:
   - The container will generate self-signed certificates in /app/certs if not present.
   - You can mount your own certs by using Docker volume mounts if needed.

5. The start.sh script ensures certs are present and starts the server.

# For custom Flask app
- Place your app.py in this directory and update start.sh to run it.
