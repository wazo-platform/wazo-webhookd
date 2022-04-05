#!/bin/bash

rm -f ca.key ca.crt server.key server.csr server.crt client.key client.csr client.crt

# CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -config ca.conf -key ca.key -out ca.crt

# Server
openssl genrsa -out server.key 4096
openssl req -new -config server.conf -key server.key -out server.csr
openssl x509 -req -days 3650 -in server.csr -CA ca.crt -CAkey ca.key -set_serial 01 -out server.crt -extfile server.conf -extensions v3_req

cat ca.crt >> server.crt

# Client
openssl genrsa -out client.key 4096
openssl req -new -config client.conf -key client.key -out client.csr
openssl x509 -req -days 3650 -in client.csr -CA ca.crt -CAkey ca.key -set_serial 01 -out client.crt -extfile server.conf

cat ca.crt >> client.crt
