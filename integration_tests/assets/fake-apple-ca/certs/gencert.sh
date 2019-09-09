#!/bin/bash

SUBJECT_CA="/C=CA/ST=Testing/L=Testing/O=Wazo/CN=ca.push.apple.com"
SUBJECT_API="/C=CA/ST=Testing/L=Testing/O=Wazo/CN=api.push.apple.com"
SUBJECT_CLIENT="/C=CA/ST=Testing/L=Testing/O=Wazo/CN=clients.push.apple.com"

rm -f ca.key ca.crt server.key server.csr server.crt client.key client.csr client.crt

# CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -subj "$SUBJECT_CA" -key ca.key -out ca.crt

# Server
openssl genrsa -out server.key 4096
openssl req -new -subj "$SUBJECT_API" -key server.key -out server.csr
openssl x509 -req -days 3650 -in server.csr -CA ca.crt -CAkey ca.key -set_serial 01 -out server.crt

cat ca.crt >> server.crt

# Client
openssl genrsa -out client.key 4096
openssl req -new -subj "$SUBJECT_CLIENT" -key client.key -out client.csr
openssl x509 -req -days 3650 -in client.csr -CA ca.crt -CAkey ca.key -set_serial 01 -out client.crt

cat ca.crt >> client.crt
