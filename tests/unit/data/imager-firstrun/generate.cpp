// firstrun.sh samples for test_imager_customisation.py, from Raspberry Pi
// Imager's own generator (src/customization_generator.cpp, Apache-2.0).
// Build against a tag's customization_generator.{cpp,h} and Qt 6 (Core,
// Network), e.g. with aqtinstall's qtbase on macOS:
//   clang++ -std=c++17 -I<imager>/src -I<imager>/src/dependencies/sha256crypt \
//     -I<imager>/src/dependencies/yescrypt -iframework <qt>/lib \
//     -I<qt>/lib/QtCore.framework/Headers -I<qt>/lib/QtNetwork.framework/Headers \
//     <imager>/src/customization_generator.cpp generate.cpp -o gen \
//     -framework QtCore -framework QtNetwork -Wl,-rpath,<qt>/lib
//   ./gen imager-<tag>-user.sh imager-<tag>-keyonly.sh
// The password and Wi-Fi key are passed pre-hashed, so the crypt functions
// are stubs. imager-1.8.5-user.sh is transcribed from 1.8.5's
// OptionsPopup.qml (same settings; 1.8.x has no Connect part).
#include "customization_generator.h"
#include <QVariantMap>
#include <QFile>
#include <cstdio>
#include <cstring>
using namespace rpi_imager;
extern "C" char *sha256_crypt(const char *, const char *) { static char s[] = "$5$stub"; return s; }
extern "C" char *yescrypt_crypt(const char *, const char *) { static char s[] = "$y$stub"; return s; }
static void out(const char *path, const QByteArray &b) { QFile f(path); f.open(QIODevice::WriteOnly); f.write(b); }
int main(int argc, char **argv) {
    const QString token = "rpuak_TESTTOKENaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    QVariantMap s;
    s["hostname"] = "kit-07";
    s["timezone"] = "Europe/Berlin";
    s["keyboard"] = "de";
    s["sshEnabled"] = true;
    s["sshPasswordAuth"] = false;
    s["sshUserName"] = "jan";
    s["sshUserPassword"] = "$5$q6XMdhfKwxRP4DgV$6OHhYS0aGsYC3ZgKcVQzO6XEBLhHH8yQSf1Am3Vf3z9";
    s["sshPublicKey"] = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnly jan@laptop";
    s["wifiSSID"] = "Classroom";
    s["wifiPasswordCrypt"] = "1b6c3f1a2e5d8c7b9a0f1e2d3c4b5a69788766554433221100ffeeddccbbaa99";
    s["recommendedWifiCountry"] = "DE";
    s["piConnectEnabled"] = true;
    s["osReleaseDate"] = "2026-10-04";
    out(argv[1], CustomisationGenerator::generateSystemdScript(s, token));
    // SSH key only, no user name: Imager uses "pi"
    QVariantMap k;
    k["hostname"] = "kit-08";
    k["sshEnabled"] = true;
    k["sshPublicKey"] = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKeyOnly jan@laptop";
    k["piConnectEnabled"] = true;
    k["osReleaseDate"] = "2026-10-04";
    out(argv[2], CustomisationGenerator::generateSystemdScript(k, token));
    return 0;
}
