# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . .
RUN npm run build

# Production stage - use a small static server
FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Ensure SPA fallback for client-side routing:
COPY ./nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
