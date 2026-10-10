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
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <atomic>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>

// Bloc de données mémoire échangé entre le thread d'acquisition et le thread d'écriture disque
struct SampleBlock {
    std::vector<std::complex<float>> data;
};

// Génère un horodatage ISO-8601 UTC conforme à la norme SigMF
static std::string getIsoTimeNow() {
    auto now = std::chrono::system_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()) % 1000;
    std::time_t tt = std::chrono::system_clock::to_time_t(now);
    std::tm tm_utc;
    gmtime_r(&tt, &tm_utc);
    std::ostringstream ss;
    ss << std::put_time(&tm_utc, "%Y-%m-%dT%H:%M:%S")
       << "." << std::setfill('0') << std::setw(3) << ms.count() << "Z";
    return ss.str();
}

// Détermine le nom du fichier de métadonnées SigMF associé
static std::string getSigmfMetaPath(const std::string &dataPath) {
    size_t dotPos = dataPath.find_last_of('.');
    if (dotPos != std::string::npos && dotPos > 0) {
        return dataPath.substr(0, dotPos) + ".sigmf-meta";
    }
    return dataPath + ".sigmf-meta";
}

// Écrit le fichier de métadonnées conforme à la spécification SigMF (v1.0.0)
static void writeSigmfMetaFile(
    const std::string &metaPath,
    const std::string &dataPath,
    double freq,
    double rate,
    double ifgr,
    double rfgr,
    size_t totalSamples,
    double durationSec,
    float peakAbs,
    int sdrOverflows,
    const std::string &startTimeIso,
    SoapySDR::Device *sdr
) {
    std::ofstream mf(metaPath);
    if (!mf.is_open()) {
        std::cerr << "[-] Attention : impossible de créer le fichier SigMF : " << metaPath << std::endl;
        return;
    }

    std::string hwLabel = "SDRplay RSP1";
    std::string apiVer = "Unknown";
    std::string hwVer = "Unknown";
    std::string antenna = "RX";

    if (sdr) {
        hwLabel = sdr->getDriverKey() + " " + sdr->getHardwareKey();
        auto hwInfo = sdr->getHardwareInfo();
        if (hwInfo.count("sdrplay_api_api_version")) apiVer = hwInfo["sdrplay_api_api_version"];
        if (hwInfo.count("sdrplay_api_hw_version")) hwVer = hwInfo["sdrplay_api_hw_version"];
        auto ants = sdr->listAntennas(SOAPY_SDR_RX, 0);
        if (!ants.empty()) antenna = ants[0];
    }

    // Extraction du nom de fichier sans chemin
    std::string dataFilename = dataPath;
    size_t slashPos = dataFilename.find_last_of("/\\");
    if (slashPos != std::string::npos) {
        dataFilename = dataFilename.substr(slashPos + 1);
    }

    mf << "{\n";
    mf << "    \"global\": {\n";
    mf << "        \"core:datatype\": \"cf32_le\",\n";
    mf << "        \"core:sample_rate\": " << std::fixed << std::setprecision(1) << rate << ",\n";
    mf << "        \"core:version\": \"1.0.0\",\n";
    mf << "        \"core:recorder\": \"vga-hamradio capture_iq (SoapySDR)\",\n";
    mf << "        \"core:hw\": \"" << hwLabel << "\",\n";
    mf << "        \"core:description\": \"I/Q SDR capture for VGA RAMDAC Radio Transmission PoC (F4JXQ)\",\n";
    mf << "        \"core:author\": \"F4JXQ / vga-hamradio\",\n";
    mf << "        \"core:license\": \"MIT\",\n";
    mf << "        \"core:num_channels\": 1,\n";
    mf << "        \"sdrplay:api_version\": \"" << apiVer << "\",\n";
    mf << "        \"sdrplay:hw_version\": \"" << hwVer << "\",\n";
    mf << "        \"vga_hamradio:data_file\": \"" << dataFilename << "\",\n";
    mf << "        \"vga_hamradio:total_samples\": " << totalSamples << ",\n";
    mf << "        \"vga_hamradio:duration_seconds\": " << std::fixed << std::setprecision(3) << durationSec << ",\n";
    mf << "        \"vga_hamradio:peak_iq\": " << std::fixed << std::setprecision(6) << peakAbs << ",\n";
    mf << "        \"vga_hamradio:overflow_count\": " << sdrOverflows << "\n";
    mf << "    },\n";
    mf << "    \"captures\": [\n";
    mf << "        {\n";
    mf << "            \"core:sample_start\": 0,\n";
    mf << "            \"core:frequency\": " << std::fixed << std::setprecision(1) << freq << ",\n";
    mf << "            \"core:datetime\": \"" << startTimeIso << "\",\n";
    mf << "            \"core:gain\": " << std::fixed << std::setprecision(1) << (ifgr + rfgr) << ",\n";
    mf << "            \"core:antenna\": \"" << antenna << "\",\n";
    mf << "            \"sdrplay:if_gain_reduction\": " << std::fixed << std::setprecision(1) << ifgr << ",\n";
    mf << "            \"sdrplay:rf_gain_reduction\": " << std::fixed << std::setprecision(1) << rfgr << "\n";
    mf << "        }\n";
    mf << "    ],\n";
    mf << "    \"annotations\": []\n";
    mf << "}\n";

    mf.close();
    std::cout << "[+] Métadonnées SigMF générées : " << metaPath << std::endl;
}

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

    std::cout << "[*] Capture SDRplay RSP1 via SoapySDR (Multithread Lockless-Buffer)" << std::endl;
    std::cout << "    Fréquence centrale : " << freq / 1e6 << " MHz" << std::endl;
    std::cout << "    Taux d'échantillons: " << rate / 1e6 << " MSps" << std::endl;
    std::cout << "    Gain RX           : " << gain << " dB (IFGR=" << ifgr << ", RFGR=" << rfgr << ")" << std::endl;
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
    // Gain fixe (AGC désactivé)
    sdr->setGainMode(SOAPY_SDR_RX, 0, false);
    sdr->setGain(SOAPY_SDR_RX, 0, "IFGR", ifgr);
    sdr->setGain(SOAPY_SDR_RX, 0, "RFGR", rfgr);
    (void)gain;

    SoapySDR::Kwargs streamArgs;
    streamArgs["bufflen"] = "65536";
    streamArgs["buffers"] = "32";
    SoapySDR::Stream *rxStream = sdr->setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32, {0}, streamArgs);
    if (!rxStream) {
        std::cerr << "[-] Échec de création du flux SoapySDR." << std::endl;
        SoapySDR::Device::unmake(sdr);
        return 1;
    }

    sdr->activateStream(rxStream);

    std::ofstream outfile(outpath, std::ios::binary);
    if (!outfile.is_open()) {
        std::cerr << "[-] Impossible d'ouvrir le fichier de sortie: " << outpath << std::endl;
        sdr->deactivateStream(rxStream);
        sdr->closeStream(rxStream);
        SoapySDR::Device::unmake(sdr);
        return 1;
    }

    // Taille de lecture optimale recommandée par le pilote (MTU)
    size_t mtu = sdr->getStreamMTU(rxStream);
    if (mtu == 0 || mtu > 131072) mtu = 65536;

    // File d'attente synchronisée pour découpler totalement la capture radio de l'écriture disque
    std::queue<SampleBlock> writeQueue;
    std::mutex queueMutex;
    std::condition_variable queueCv;
    std::atomic<bool> captureFinished(false);
    std::atomic<size_t> diskQueueOverflows(0);

    // Thread d'écriture asynchrone sur disque
    std::thread writerThread([&]() {
        while (true) {
            SampleBlock block;
            {
                std::unique_lock<std::mutex> lock(queueMutex);
                queueCv.wait(lock, [&]() {
                    return !writeQueue.empty() || captureFinished.load();
                });

                if (writeQueue.empty() && captureFinished.load()) {
                    break;
                }

                block = std::move(writeQueue.front());
                writeQueue.pop();
            }

            if (!block.data.empty()) {
                outfile.write(reinterpret_cast<const char*>(block.data.data()),
                              block.data.size() * sizeof(std::complex<float>));
            }
        }
    });

    const size_t totalSamplesTarget = static_cast<size_t>(duration * rate);
    size_t totalSamplesSaved = 0;
    float peakAbs = 0.0f;
    int sdrOverflowCount = 0;

    std::vector<std::complex<float>> rxBuffer(mtu);

    // Enregistrement de l'horodatage précis du premier échantillon
    std::string captureStartTimeIso = getIsoTimeNow();

    std::cout << "[+] Enregistrement en cours..." << std::flush;

    while (totalSamplesSaved < totalSamplesTarget) {
        int flags = 0;
        long long timeNs = 0;
        void *buffs[] = { rxBuffer.data() };

        // Toujours demander la taille complète mtu pour ne jamais désynchroniser les buffers internes SDRplay
        int ret = sdr->readStream(rxStream, buffs, mtu, flags, timeNs, 2000000);
        if (ret < 0) {
            if (ret == SOAPY_SDR_OVERFLOW) {
                sdrOverflowCount++;
                continue;
            }
            std::cerr << "\n[-] Erreur de lecture SoapySDR: " << ret << std::endl;
            break;
        }

        if (flags & SOAPY_SDR_OVERFLOW) {
            sdrOverflowCount++;
        }

        if (ret > 0) {
            // Tronquer uniquement au dernier bloc pour atteindre exactement la durée demandée
            size_t samplesToTake = std::min(static_cast<size_t>(ret), totalSamplesTarget - totalSamplesSaved);

            for (size_t k = 0; k < samplesToTake; ++k) {
                float m = std::max(std::abs(rxBuffer[k].real()), std::abs(rxBuffer[k].imag()));
                if (m > peakAbs) peakAbs = m;
            }

            SampleBlock block;
            block.data.assign(rxBuffer.begin(), rxBuffer.begin() + samplesToTake);

            {
                std::lock_guard<std::mutex> lock(queueMutex);
                if (writeQueue.size() > 256) {
                    diskQueueOverflows++;
                }
                writeQueue.push(std::move(block));
            }
            queueCv.notify_one();

            totalSamplesSaved += samplesToTake;
        }
    }

    // Signal de fin de capture pour le thread d'écriture
    captureFinished.store(true);
    queueCv.notify_all();

    if (writerThread.joinable()) {
        writerThread.join();
    }

    std::cout << " Terminé ! (" << totalSamplesSaved << " échantillons écrits, crête I/Q = " << peakAbs;
    if (sdrOverflowCount > 0 || diskQueueOverflows.load() > 0) {
        std::cout << ", ⚠️ OVERFLOWS SDR = " << sdrOverflowCount
                  << ", QUEUE OVERFLOWS = " << diskQueueOverflows.load();
    } else {
        std::cout << ", zéro overflow";
    }
    std::cout << ")" << std::endl;

    outfile.close();

    // Génération automatique du fichier sidecar SigMF (.sigmf-meta)
    std::string sigmfMetaPath = getSigmfMetaPath(outpath);
    writeSigmfMetaFile(
        sigmfMetaPath,
        outpath,
        freq,
        rate,
        ifgr,
        rfgr,
        totalSamplesSaved,
        static_cast<double>(totalSamplesSaved) / rate,
        peakAbs,
        sdrOverflowCount,
        captureStartTimeIso,
        sdr
    );

    sdr->deactivateStream(rxStream);
    sdr->closeStream(rxStream);
    SoapySDR::Device::unmake(sdr);

    return 0;
}
