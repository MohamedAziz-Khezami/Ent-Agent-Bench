# ts-executor.Dockerfile — the UNTRUSTED container: runs only the model's
# generated TS code. Fully separate from js-executor.Dockerfile — this is
# the only executor with the `typescript` npm package, used for real
# semantic type-checking (ts.createProgram), not just syntax stripping. No
# access to src/db/ or src/core/ — this container can only reach data
# through a network call to the tool-server.
FROM node:22-alpine

WORKDIR /app

COPY src/executors/ts_executor/package.json src/executors/ts_executor/package-lock.json ./
RUN npm ci --omit=dev

COPY src/executors/ts_executor/ .

EXPOSE 8001

CMD ["node", "exec_server.js"]
