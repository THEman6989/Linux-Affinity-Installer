#include "tray_icon.h"

#include <QGuiApplication>
#include <QIcon>
#include <QPixmap>

#include <cstdlib>
#include <iostream>

int main(int argc, char **argv)
{
    qputenv("QT_QPA_PLATFORM", "offscreen");
    QGuiApplication app(argc, argv);

    const QIcon active = createTrayIcon(true);
    const QIcon inactive = createTrayIcon(false);
    if (active.isNull() || inactive.isNull()) {
        std::cerr << "tray icons must not be null\n";
        return 1;
    }
    if (active.pixmap(32, 32).isNull() || inactive.pixmap(32, 32).isNull()) {
        std::cerr << "tray icons must publish embedded pixmaps\n";
        return 1;
    }
    std::cout << "tray icon tests passed\n";
    return 0;
}
