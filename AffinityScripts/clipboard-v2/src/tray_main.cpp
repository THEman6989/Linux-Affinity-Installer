#include "tray_icon.h"

#include <QAction>
#include <QApplication>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QIcon>
#include <QMenu>
#include <QProcess>
#include <QSignalBlocker>
#include <QSystemTrayIcon>
#include <QTimer>

#include <cstdio>
#include <utility>

namespace {

constexpr auto DefaultService = "affinity-clipboard-v2.service";

bool serviceIsActive(const QString &service)
{
    return QProcess::execute(QStringLiteral("systemctl"),
                             {QStringLiteral("--user"),
                              QStringLiteral("is-active"),
                              QStringLiteral("--quiet"), service})
        == 0;
}

int setServiceActive(const QString &service, bool active)
{
    return QProcess::execute(
        QStringLiteral("systemctl"),
        {QStringLiteral("--user"),
         active ? QStringLiteral("start") : QStringLiteral("stop"), service});
}

class TrayController final : public QObject
{
public:
    explicit TrayController(QString service, QObject *parent = nullptr)
        : QObject(parent), service_(std::move(service)), menu_(), tray_(),
          toggle_(QStringLiteral("Affinity PNG-Clipboard aktiv"), &menu_),
          refresh_(QStringLiteral("Status aktualisieren"), &menu_),
          quit_(QStringLiteral("Tray-Symbol beenden"), &menu_)
    {
        toggle_.setCheckable(true);
        menu_.addAction(&toggle_);
        menu_.addAction(&refresh_);
        menu_.addSeparator();
        menu_.addAction(&quit_);

        tray_.setContextMenu(&menu_);
        tray_.setIcon(createTrayIcon(false));
        tray_.setVisible(true);

        connect(&toggle_, &QAction::toggled, this, [this](bool active) {
            const int result = setServiceActive(service_, active);
            if (result == 0) {
                tray_.showMessage(
                    QStringLiteral("Affinity PNG-Clipboard"),
                    active ? QStringLiteral("Aktiviert: PNG und Dateiname werden gemeinsam angeboten.")
                           : QStringLiteral("Deaktiviert: normales Plasma-Clipboard ist unverändert."),
                    QSystemTrayIcon::Information, 3500);
            } else {
                tray_.showMessage(QStringLiteral("Affinity PNG-Clipboard"),
                                  QStringLiteral("Dienst konnte nicht umgeschaltet werden."),
                                  QSystemTrayIcon::Critical, 5000);
            }
            QTimer::singleShot(300, this, [this] { updateStatus(); });
        });
        connect(&refresh_, &QAction::triggered, this,
                [this] { updateStatus(); });
        connect(&quit_, &QAction::triggered, qApp, &QCoreApplication::quit);

        timer_.setInterval(3000);
        connect(&timer_, &QTimer::timeout, this, [this] { updateStatus(); });
        timer_.start();
        updateStatus();
    }

private:
    void updateStatus()
    {
        const bool active = serviceIsActive(service_);
        const QSignalBlocker blocker(&toggle_);
        toggle_.setChecked(active);
        tray_.setIcon(createTrayIcon(active));
        tray_.setToolTip(
            active ? QStringLiteral("Affinity PNG-Clipboard: aktiv")
                   : QStringLiteral("Affinity PNG-Clipboard: aus"));
    }

    QString service_;
    QMenu menu_;
    QSystemTrayIcon tray_;
    QAction toggle_;
    QAction refresh_;
    QAction quit_;
    QTimer timer_;
};

} // namespace

int main(int argc, char **argv)
{
    bool statusMode = false;
    QString service = QString::fromLatin1(DefaultService);
    for (int index = 1; index < argc; ++index) {
        const QString argument = QString::fromLocal8Bit(argv[index]);
        if (argument == QStringLiteral("--status")) {
            statusMode = true;
        } else if (argument == QStringLiteral("--service") && index + 1 < argc) {
            service = QString::fromLocal8Bit(argv[++index]);
        }
    }

    if (statusMode) {
        QCoreApplication app(argc, argv);
        std::puts(serviceIsActive(service) ? "active" : "inactive");
        return 0;
    }

    QApplication app(argc, argv);
    QApplication::setQuitOnLastWindowClosed(false);
    TrayController controller(service);
    return app.exec();
}
