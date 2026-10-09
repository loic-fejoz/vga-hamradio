#include <SoapySDR/Device.hpp>
#include <SoapySDR/Formats.hpp>
#include <iostream>
#include <fstream>
#include <vector>
#include <complex>
#include <string>
#include <cmath>
#include <algorithm>
#include <cstdlib>

int main(int argc, char** argv) {
    double freq = 14230000.0;
    double rate = 250000.0;
    double gain = 35.0;
    double duration = 2.0;
    double ifgr = 40.0;
    double rfgr = 0.0;
    std::string outpath = "capture.cf32";

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-f" && i + 1 < argc) freq = std::atof(argv[++i]);
        else if (arg == "-s" && i + 1 < argc) rate = std::atof(argv[++i]);
        else if (arg == "-g" && i + 1 < argc) gain = std::atof(argv[++i]);
        else if (arg == "-d" && i + 1 < argc) duration = std::atof(argv[++i]);
        else if (arg == "-I" && i + 1 < argc) ifgr = std::atof(argv[++i]);
        else if (arg == "-R" && i + 1 < argc) rfgr = std::atof(argv[++i]);
        else if (arg == "-o" && i + 1 < argc) outpath = argv[++i];
    }

    std::cout << "[*] Capture SDRplay RSP1 via SoapySDR" << std::endl;
    std::cout << "    Fréquence centrale : " << freq / 1e6 << " MHz" << std::endl;
    std::cout << "    Taux d'échantillons: " << rate / 1e6 << " MSps" << std::endl;
    std::cout << "    Gain RX           : " << gain << " dB" << std::endl;
    std::cout << "    Durée             : " << duration << " s" << std::endl;
    std::cout << "    Fichier de sortie : " << outpath << std::endl;

    SoapySDR::Kwargs args;
    args["driver"] = "sdrplay";
    SoapySDR::Device *sdr = nullptr;

    try {
        sdr = SoapySDR::Device::make(args);
    } catch (const std::exception &ex) {
        std::cerr << "[-] Erreur ouverture SDR: " << ex.what() << std::endl;
        return 1;
    }

    if (!sdr) {
        std::cerr << "[-] Aucun périphérique SDRplay trouvé." << std::endl;
        return 1;
    }

    sdr->setSampleRate(SOAPY_SDR_RX, 0, rate);
    sdr->setFrequency(SOAPY_SDR_RX, 0, freq);
    // AGC désactivé : gain fixe pour que les niveaux soient comparables dans le temps
    sdr->setGainMode(SOAPY_SDR_RX, 0, false);
    sdr->setGain(SOAPY_SDR_RX, 0, "IFGR", ifgr);
    sdr->setGain(SOAPY_SDR_RX, 0, "RFGR", rfgr);
    (void)gain;

    SoapySDR::Kwargs streamArgs;
    streamArgs["bufflen"] = "131072";
    streamArgs["buffers"] = "16";
    SoapySDR::Stream *rxStream = sdr->setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32, {0}, streamArgs);
    sdr->activateStream(rxStream);

    std::ofstream outfile(outpath, std::ios::binary);
    if (!outfile.is_open()) {
        std::cerr << "[-] Impossible d'ouvrir le fichier de sortie: " << outpath << std::endl;
        sdr->deactivateStream(rxStream);
        sdr->closeStream(rxStream);
        SoapySDR::Device::unmake(sdr);
        return 1;
    }

    const size_t blockSize = 131072;
    std::vector<std::complex<float>> buffer(blockSize);
    size_t totalSamplesTarget = static_cast<size_t>(duration * rate);
    size_t totalSamplesRead = 0;
    float peakAbs = 0.0f;
    int overflowCount = 0;

    std::cout << "[+] Enregistrement en cours..." << std::flush;

    while (totalSamplesRead < totalSamplesTarget) {
        int flags = 0;
        long long timeNs = 0;
        size_t toRead = std::min(blockSize, totalSamplesTarget - totalSamplesRead);
        void *buffs[] = { buffer.data() };
        int ret = sdr->readStream(rxStream, buffs, toRead, flags, timeNs, 2000000);
        if (ret < 0) {
            if (ret == SOAPY_SDR_OVERFLOW) {
                overflowCount++;
                continue;
            }
            std::cerr << "\n[-] Erreur de lecture SoapySDR: " << ret << std::endl;
            break;
        }
        if (flags & SOAPY_SDR_OVERFLOW) {
            overflowCount++;
        }
        outfile.write(reinterpret_cast<const char*>(buffer.data()), ret * sizeof(std::complex<float>));
        for (int k = 0; k < ret; ++k) {
            float m = std::max(std::abs(buffer[k].real()), std::abs(buffer[k].imag()));
            if (m > peakAbs) peakAbs = m;
        }
        totalSamplesRead += ret;
    }

    std::cout << " Terminé ! (" << totalSamplesRead << " échantillons écrits, crête I/Q = " << peakAbs;
    if (overflowCount > 0) {
        std::cout << ", ⚠️ OVERFLOWS DÉTECTÉS = " << overflowCount;
    } else {
        std::cout << ", zéro overflow";
    }
    std::cout << ")" << std::endl;

    outfile.close();
    sdr->deactivateStream(rxStream);
    sdr->closeStream(rxStream);
    SoapySDR::Device::unmake(sdr);

    return 0;
}
