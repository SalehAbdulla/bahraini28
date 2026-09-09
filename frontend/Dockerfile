# syntax=docker/dockerfile:1
# Builds the Vite/React SPA. The compose `frontend` service copies /dist into
# a shared volume that Caddy serves (see deploy/docker-compose.yml).
FROM node:22-alpine AS build
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM alpine:3
WORKDIR /out
COPY --from=build /build/dist/ /dist/
