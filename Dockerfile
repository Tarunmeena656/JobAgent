# One image with the API and the built frontend. Used by render.yaml; docker-compose.yml still runs them separately.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY --from=web /web/dist /srv/frontend/dist

ENV STORAGE_DIR=/data/storage
EXPOSE 8000
CMD ["sh", "scripts/start.sh"]
