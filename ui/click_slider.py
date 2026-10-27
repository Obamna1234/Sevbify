"""A slider that jumps to where you click (like Spotify's progress and volume bars), and can still be dragged."""
from PyQt6.QtWidgets import QSlider, QStyle, QStyleOptionSlider
from PyQt6.QtCore import Qt


class ClickSlider(QSlider):
    def _value_at(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt,
                                             QStyle.SubControl.SC_SliderGroove, self)
        handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt,
                                             QStyle.SubControl.SC_SliderHandle, self)
        if self.orientation() == Qt.Orientation.Horizontal:
            span = max(1, groove.width() - handle.width())
            offset = pos.x() - groove.x() - handle.width() // 2
        else:
            span = max(1, groove.height() - handle.height())
            offset = pos.y() - groove.y() - handle.height() // 2
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), max(0, min(offset, span)), span,
                                              opt.upsideDown)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            # Move the handle under the pointer first; the normal press then grabs it, so the user can keep
            # dragging, and releasing seeks (sliderPressed / sliderReleased fire as usual).
            self.setValue(self._value_at(e.position().toPoint()))
        super().mousePressEvent(e)
