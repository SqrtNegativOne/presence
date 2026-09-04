# frontend/Dockerfile
FROM oven/bun:1-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

# Copy source code
COPY . .

EXPOSE 5173

# This makes Vite listen on 0.0.0.0 so the container port is reachable.
CMD ["bun", "run", "dev", "--host"]
