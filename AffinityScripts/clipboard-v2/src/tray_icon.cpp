#include "tray_icon.h"

#include <QColor>
#include <QImage>
#include <QPainter>
#include <QPen>
#include <QPixmap>

QIcon createTrayIcon(bool active)
{
    QImage image(64, 64, QImage::Format_ARGB32_Premultiplied);
    image.fill(Qt::transparent);

    QPainter painter(&image);
    painter.setRenderHint(QPainter::Antialiasing, true);
    painter.setPen(Qt::NoPen);
    painter.setBrush(active ? QColor(QStringLiteral("#16856b"))
                            : QColor(QStringLiteral("#667085")));
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14);

    QPen whitePen(Qt::white, 5, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin);
    painter.setPen(whitePen);
    painter.setBrush(Qt::NoBrush);
    painter.drawRoundedRect(16, 15, 32, 38, 5, 5);
    painter.drawLine(24, 12, 40, 12);
    painter.drawLine(24, 26, 40, 26);
    painter.drawLine(24, 37, 40, 37);
    painter.end();

    QIcon icon;
    icon.addPixmap(QPixmap::fromImage(image));
    return icon;
}
