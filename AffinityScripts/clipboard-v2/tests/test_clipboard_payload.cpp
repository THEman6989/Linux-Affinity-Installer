#include "clipboard_payload.h"

#include <QCoreApplication>
#include <QFile>
#include <QMimeData>
#include <QTemporaryDir>
#include <QUrl>

#include <cstdlib>
#include <iostream>
#include <memory>

namespace {

void require(bool condition, const char *message)
{
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}

QString writeFile(const QTemporaryDir &directory, const QString &name,
                  const QByteArray &data)
{
    const QString path = directory.filePath(name);
    QFile file(path);
    require(file.open(QIODevice::WriteOnly), "test file must open");
    require(file.write(data) == data.size(), "test file must be complete");
    return path;
}

} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QTemporaryDir directory;
    require(directory.isValid(), "temporary directory must be valid");

    const QByteArray png("\x89PNG\r\n\x1a\nembedded-test-data", 26);
    const QString pngPath = writeFile(directory, QStringLiteral("named image.png"), png);

    QString error;
    std::unique_ptr<QMimeData> mime = buildClipboardMimeData(pngPath, &error);
    require(mime != nullptr, "PNG must produce MIME data");
    require(error.isEmpty(), "successful build must not report an error");
    require(mime->hasFormat(QStringLiteral("image/png")), "image/png must be offered");
    require(mime->hasFormat(QStringLiteral("text/uri-list")), "text/uri-list must be offered");
    require(mime->hasFormat(QStringLiteral("application/x-kde4-urilist")),
            "KDE URI list must be offered");
    require(mime->hasFormat(QStringLiteral("application/x-affinity-clipboard-v2")),
            "self-feedback marker must be offered");
    require(mime->data(QStringLiteral("image/png")) == png,
            "PNG bytes must remain byte-identical");
    require(mime->urls().size() == 1, "exactly one file URL must be offered");
    require(mime->urls().constFirst().toLocalFile() == pngPath,
            "file URL must preserve the original filename");

    const QByteArray kdeUri = mime->data(QStringLiteral("application/x-kde4-urilist"));
    require(kdeUri.contains("named%20image.png"), "KDE URI must preserve encoded filename");

    const QString jpgPath = writeFile(directory, QStringLiteral("wrong.jpg"), png);
    error.clear();
    mime = buildClipboardMimeData(jpgPath, &error);
    require(mime == nullptr, "non-PNG input must be rejected");
    require(!error.isEmpty(), "rejected input must explain the error");

    const QString oversizedPath =
        writeFile(directory, QStringLiteral("oversized.png"), png);
    error.clear();
    mime = buildClipboardMimeData(oversizedPath, &error, png.size() - 1);
    require(mime == nullptr, "opened PNG bytes beyond max must be rejected");
    require(!error.isEmpty(), "oversized input must explain the error");

    std::cout << "clipboard payload tests passed\n";
    return 0;
}
