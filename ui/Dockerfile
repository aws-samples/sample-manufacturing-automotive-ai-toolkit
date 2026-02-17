# Step 1: Use Node.js base image
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

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Change ownership to non-root user
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Add health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000 || exit 1

# Start the app
CMD ["npm", "start"]
