#include "clipboard_payload.h"

#include <QClipboard>
#include <QCoreApplication>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeData>
#include <QTextStream>
#include <QTimer>

#include <memory>
#include <cstdio>

namespace {

int describe(const QString &filePath)
{
    QString error;
    std::unique_ptr<QMimeData> mime = buildClipboardMimeData(filePath, &error);
    if (!mime) {
        QTextStream(stderr) << error << '\n';
        return 1;
    }

    QJsonArray formats;
    for (const QString &format : mime->formats()) {
        formats.append(format);
    }
    const QJsonObject description{
        {QStringLiteral("file"), filePath},
        {QStringLiteral("formats"), formats},
    };
    QTextStream(stdout) << QJsonDocument(description).toJson(QJsonDocument::Compact)
                        << '\n';
    return 0;
}

} // namespace

int main(int argc, char **argv)
{
    if (argc == 3 && QByteArray(argv[1]) == "--describe") {
        return describe(QString::fromLocal8Bit(argv[2]));
    }
    if (argc != 2) {
        QTextStream(stderr) << "usage: affinity-clipboard-owner PNG_FILE\n";
        return 2;
    }

    qputenv("QT_QPA_PLATFORM", "xcb");
    QGuiApplication app(argc, argv);

    QString error;
    std::unique_ptr<QMimeData> mime =
        buildClipboardMimeData(QString::fromLocal8Bit(argv[1]), &error);
    if (!mime) {
        QTextStream(stderr) << error << '\n';
        return 1;
    }

    QClipboard *clipboard = QGuiApplication::clipboard();
    bool initialized = false;
    QObject::connect(clipboard, &QClipboard::changed, &app,
                     [&](QClipboard::Mode mode) {
                         if (mode == QClipboard::Clipboard && initialized
                             && !clipboard->ownsClipboard()) {
                             app.quit();
                         }
                     });

    clipboard->setMimeData(mime.release(), QClipboard::Clipboard);
    QTimer::singleShot(0, &app, [&] {
        initialized = true;
        if (!clipboard->ownsClipboard()) {
            QTextStream(stderr) << "failed to own the X11 clipboard\n";
            app.exit(1);
            return;
        }
        QTextStream out(stdout);
        out << "Affinity multi-format clipboard ready\n";
        out.flush();
    });

    return app.exec();
}
