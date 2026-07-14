#pragma once

#include <QtGlobal>

#include <memory>

class QMimeData;
class QString;

constexpr qint64 DefaultMaxPngBytes = 256LL * 1024LL * 1024LL;

std::unique_ptr<QMimeData> buildClipboardMimeData(const QString &filePath,
                                                  QString *error,
                                                  qint64 maxBytes = DefaultMaxPngBytes);
