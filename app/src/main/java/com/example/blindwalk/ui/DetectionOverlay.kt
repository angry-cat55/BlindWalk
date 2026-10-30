package com.example.blindwalk.ui

import android.graphics.Bitmap
import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.blindwalk.inference.Recognition

// 검출 표시는 시각 보조용이다. 음성은 기존 공통 안내 결과에서 선택한다.
@Composable
fun DetectionOverlay(
    objects: List<Recognition>,
    selectedId: Int?,
    modifier: Modifier = Modifier,
    frameBitmap: Bitmap? = null,
) {
    Canvas(modifier.clearAndSetSemantics {}) {
        val transform = OverlayTransform.fit(size.width, size.height)

        frameBitmap?.let { bmp ->
            if (!bmp.isRecycled) {
                drawImage(
                    image = bmp.asImageBitmap(),
                    dstOffset = IntOffset(transform.left.toInt(), transform.top.toInt()),
                    dstSize = IntSize((640f * transform.scale).toInt(), (480f * transform.scale).toInt()),
                )
            }
        }

        val green = Color(0xFF9CF2C7)
        val amber = Color(0xFFFFD27B)
        val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = 12.sp.toPx()
            typeface = android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL)
        }

        for (obj in objects) {
            if (obj.bbox.size != 4) continue
            val selected = obj.id == selectedId
            val color = if (selected) amber else Color(0xFFD6EEE6)
            val tactile = obj.className in setOf("tactile_line", "tactile_dot")

            // 점자블록은 모델이 반환한 실제 contour만 채운다. 경로선을 만들지 않는다.
            if (tactile) {
                val points = obj.contour?.filter { it.size >= 2 }.orEmpty()
                if (points.size >= 3) {
                    val path = Path().apply {
                        moveTo(transform.x(points[0][0].toFloat()), transform.y(points[0][1].toFloat()))
                        points.drop(1).forEach { lineTo(transform.x(it[0].toFloat()), transform.y(it[1].toFloat())) }
                        close()
                    }
                    drawPath(path, green.copy(alpha = .23f))
                    drawPath(path, if (selected) amber else green, style = Stroke(2.dp.toPx()))
                }
            }

            val left = transform.x(obj.bbox[0].toFloat())
            val top = transform.y(obj.bbox[1].toFloat())
            val right = transform.x(obj.bbox[2].toFloat())
            val bottom = transform.y(obj.bbox[3].toFloat())
            if (right <= left || bottom <= top) continue
            drawRoundRect(color, Offset(left, top), Size(right - left, bottom - top),
                CornerRadius(6.dp.toPx()), style = Stroke((if (selected) 3f else 1.5f).dp.toPx()))

            val distanceText = obj.distanceM?.let { " · %.1fm".format(it) } ?: ""
            val label = koreanLabel(obj.className) + distanceText + if (selected) " · 🎯 안내" else ""
            val pad = 4.dp.toPx()
            val width = text.measureText(label) + pad * 2
            val height = text.fontMetrics.run { descent - ascent } + pad
            val x = left.coerceIn(0f, (size.width - width).coerceAtLeast(0f))
            val y = (top - height - 3.dp.toPx()).coerceAtLeast(0f)
            drawRoundRect(if (selected) amber else Color(0xFF273B35), Offset(x, y), Size(width, height), CornerRadius(4.dp.toPx()))
            text.color = if (selected) 0xFF30240D.toInt() else android.graphics.Color.WHITE
            drawContext.canvas.nativeCanvas.drawText(label, x + pad, y + pad / 2 - text.fontMetrics.ascent, text)
        }
    }
}

// 모델 클래스 순서와 무관하게 이름으로 표시하며, 알 수 없는 이름은 그대로 보여준다.
private fun koreanLabel(name: String): String = when (name) {
    "tactile_line" -> "🟡 선형블록"
    "tactile_dot" -> "🟡 점형블록"
    "stairs" -> "🪜 계단"
    "curb" -> "연석"
    "crosswalk" -> "🚶 횡단보도"
    "bollard" -> "🛑 볼라드"
    "pole" -> "기둥"
    "tree_trunk" -> "가로수"
    "bicycle" -> "🚲 자전거"
    "movable_signage" -> "🪧 입간판"
    "vehicle" -> "🚗 차량"
    "person" -> "👤 사람"
    "traffic_light" -> "신호등"
    "facility" -> "🏢 시설물"
    "overhang" -> "돌출물"
    "elevator" -> "🛗 승강기"
    "elevator_sign" -> "🛗 승강기 표지"
    "toilet_sign" -> "화장실 표지"
    else -> name
}
