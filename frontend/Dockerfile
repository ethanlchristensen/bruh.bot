# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Accept build arguments
ARG VITE_BACKEND_API_URL

# Set as environment variables for Vite
ENV VITE_BACKEND_API_URL=$VITE_BACKEND_API_URL

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the Vite app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy nginx config as template (nginx will auto-process with envsubst)
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Copy built assets from Vite
COPY --from=build /app/dist /usr/share/nginx/html

# Set default API_HOST (will be overridden by docker-compose)
ENV API_HOST=config-api-dev

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]