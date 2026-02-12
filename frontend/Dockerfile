# Dockerfile for ThumbsUp Frontend
# Build stage
FROM node:18 AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ .
RUN npm run build

# Production stage - Nginx
FROM nginx:alpine

WORKDIR /usr/share/nginx/html

RUN rm -rf ./*

COPY --from=build /app/dist ./

COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY frontend/start_webserver.sh /start_webserver.sh
RUN chmod +x /start_webserver.sh

RUN mkdir -p /app/pki /etc/nginx/certs
COPY backend/pki/*.pem /app/pki/

EXPOSE 443

ENTRYPOINT ["/start_webserver.sh"]
