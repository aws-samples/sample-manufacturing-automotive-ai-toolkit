# Step 1: Use Node.js base image
# FROM --platform=linux/amd64 public.ecr.aws/docker/library/node:18-alpine3.21 AS builder
# Step 1: Use Node.js base image with explicit platform
FROM --platform=linux/amd64 public.ecr.aws/docker/library/node:18-alpine3.21 AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Remove package-lock.json and regenerate for current platform
# This ensures sharp and other native deps are installed for the correct architecture
RUN rm -f package-lock.json && \
    npm install --only=production && \
    npm rebuild sharp

# Copy pre-built application
COPY .next ./.next
COPY public ./public
COPY app ./app

# Expose port
EXPOSE 3000

# Start the app
CMD ["npm", "start"]
