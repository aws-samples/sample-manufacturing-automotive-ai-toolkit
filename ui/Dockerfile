# Step 1: Use Node.js base image
# FROM --platform=linux/amd64 public.ecr.aws/docker/library/node:18-alpine3.21 AS builder
FROM public.ecr.aws/docker/library/node:18-alpine3.21 AS builder

WORKDIR /app

# Copy package.json and install production dependencies
COPY package.json package-lock.json ./
RUN npm ci --only=production

# Copy pre-built application
COPY .next ./.next
COPY public ./public
COPY app ./app

# Expose port
EXPOSE 3000

# Start the app
CMD ["npm", "start"]

