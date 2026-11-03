#!/bin/bash

sudo ip link set can1 type can bitrate 1000000
sudo ip link set can2 type can bitrate 1000000
sudo ip link set can1 up
sudo ip link set can2 up
