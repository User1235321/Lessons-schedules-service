ARG MINIO_COMMIT=7aac2a2c5b7c882e68c1ce017d8256be2feea27f

FROM golang:1.24.8-alpine3.22 AS build

ARG MINIO_COMMIT

RUN apk add --no-cache ca-certificates git

WORKDIR /src

RUN git init \
    && git remote add origin https://github.com/minio/minio.git \
    && git fetch --depth=1 origin "${MINIO_COMMIT}" \
    && git checkout --detach FETCH_HEAD

ENV CGO_ENABLED=0

RUN go build -tags kqueue -trimpath \
    -ldflags "$(go run buildscripts/gen-ldflags.go)" \
    -o /out/minio .

FROM alpine:3.22

ARG MINIO_COMMIT

LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="${MINIO_COMMIT}"

RUN apk add --no-cache ca-certificates

COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /src/CREDITS /licenses/

EXPOSE 9000 9001

ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
