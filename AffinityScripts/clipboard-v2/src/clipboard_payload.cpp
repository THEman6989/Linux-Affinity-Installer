#include "clipboard_payload.h"

#include <QFile>
#include <QFileInfo>
#include <QMimeData>
#include <QString>
#include <QUrl>

namespace {
const QByteArray PngSignature("\x89PNG\r\n\x1a\n", 8);
const QString SelfFeedbackMimeType =
    QStringLiteral("application/x-affinity-clipboard-v2");

std::unique_ptr<QMimeData> fail(QString *error, const QString &message)
{
    if (error) {
        *error = message;
    }
    return nullptr;
}
} // namespace

std::unique_ptr<QMimeData> buildClipboardMimeData(const QString &filePath,
                                                  QString *error,
                                                  qint64 maxBytes)
{
    if (error) {
        error->clear();
    }

    const QFileInfo info(filePath);
    if (!info.isFile()) {
        return fail(error, QStringLiteral("not a regular file"));
    }
    if (info.suffix().compare(QStringLiteral("png"), Qt::CaseInsensitive) != 0) {
        return fail(error, QStringLiteral("only PNG files are supported"));
    }
    if (maxBytes <= 0) {
        return fail(error, QStringLiteral("maximum PNG size must be positive"));
    }
    if (info.size() <= 0) {
        return fail(error, QStringLiteral("PNG size is outside the supported range"));
    }

    QFile file(info.absoluteFilePath());
    if (!file.open(QIODevice::ReadOnly)) {
        return fail(error, file.errorString());
    }
    const QByteArray png = file.read(maxBytes + 1);
    if (file.error() != QFile::NoError) {
        return fail(error, QStringLiteral("PNG could not be read completely"));
    }
    if (png.size() <= 0 || png.size() > maxBytes) {
        return fail(error, QStringLiteral("PNG size is outside the supported range"));
    }
    if (!png.startsWith(PngSignature)) {
        return fail(error, QStringLiteral("file does not have a PNG signature"));
    }

    const QUrl fileUrl = QUrl::fromLocalFile(info.absoluteFilePath());
    QByteArray uriList = fileUrl.toEncoded();
    uriList.append("\r\n");

    auto mime = std::make_unique<QMimeData>();
    mime->setUrls({fileUrl});
    mime->setData(QStringLiteral("application/x-kde4-urilist"), uriList);
    mime->setData(QStringLiteral("image/png"), png);
    mime->setData(SelfFeedbackMimeType, QByteArrayLiteral("1"));
    return mime;
}
