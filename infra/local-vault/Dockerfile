# The locked teardown vault for local testing (§23): MinIO and its client, built from source at pinned releases,
# because MinIO no longer publishes community images (V-Q1). MinIO is AGPL-3.0 and is used only locally, never shipped.
FROM golang:1.24-alpine AS build
ARG MINIO_RELEASE=RELEASE.2025-04-22T22-12-26Z
ARG MC_RELEASE=RELEASE.2025-04-16T18-13-26Z
RUN apk add --no-cache git
RUN git clone --depth 1 --branch "${MINIO_RELEASE}" https://github.com/minio/minio /src/minio \
 && cd /src/minio && CGO_ENABLED=0 go build -trimpath -o /out/minio .
RUN git clone --depth 1 --branch "${MC_RELEASE}" https://github.com/minio/mc /src/mc \
 && cd /src/mc && CGO_ENABLED=0 go build -trimpath -o /out/mc .

FROM alpine:3.20
RUN apk add --no-cache bash curl
COPY --from=build /out/minio /out/mc /usr/local/bin/
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
