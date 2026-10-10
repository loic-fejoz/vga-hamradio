CC ?= gcc
CFLAGS ?= -std=c99 -O3 -Wall -Wextra
CXX ?= g++
CXXFLAGS ?= -std=c++11 -O3 -Wall -Wextra
LIBS_SDR = -lSoapySDR -lpthread
LIBS_GL = -lX11 -lGL -lm -lpthread

all: capture_iq vga_tx_gpu

capture_iq: capture_iq.cpp
	$(CXX) $(CXXFLAGS) -o capture_iq capture_iq.cpp $(LIBS_SDR)

vga_tx_gpu: vga_tx_gpu.c
	$(CC) $(CFLAGS) -o vga_tx_gpu vga_tx_gpu.c $(LIBS_GL)

clean:
	rm -f capture_iq vga_tx_gpu

spice:
	ngspice -b stage_adaptation_vga.cir

.PHONY: spice clean
