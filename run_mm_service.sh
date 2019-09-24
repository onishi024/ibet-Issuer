#!/bin/bash

trap "exit 0" SIGINT SIGTERM

while true
do
  sleep 60 & wait $!
done
