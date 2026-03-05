# frontend/Dockerfile
FROM node:20-slim

WORKDIR /app

# Install dependencies first (layer caching — same trick as backend).
# package-lock.json is the lockfile npm generates; the * means "copy it if it exists."
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

EXPOSE 5173

# "-- --host" passes --host to the underlying vite command.
# This makes Vite listen on 0.0.0.0 so the container port is reachable.
CMD ["npm", "run", "dev", "--", "--host"]
