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

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from Vite
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]