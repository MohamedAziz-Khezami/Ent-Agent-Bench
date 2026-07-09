# js-executor.Dockerfile — the UNTRUSTED container: runs only the model's
# generated JS code. Fully separate from ts-executor.Dockerfile — this image
# depends only on `acorn` (a plain JS parser), never `typescript`. No access
# to src/db/ or src/core/ — this container can only reach data through a
# network call to the tool-server.
FROM node:22-alpine

WORKDIR /app

COPY src/executors/js_executor/package.json src/executors/js_executor/package-lock.json ./
RUN npm ci --omit=dev

COPY src/executors/js_executor/ .

EXPOSE 8001

CMD ["node", "exec_server.js"]
