package com.example.blindwalk.inference

import kotlin.math.*

// decode/infer 직후 id는 후보 번호다. 실제 앱은 ObjectTracker가 세션 추적 ID로 교체한다.
data class Recognition(
    val id: Int,
    val className: String,
    val confidence: Float,
    val bbox: List<Int>,
    val contour: List<List<Int>>?,
    val distanceM: Float? = null,
)

// 저장소의 YOLO11n-seg TFLite 출력: [1,4+클래스+마스크계수,8400].
// 첫 4채널은 정규화 cx/cy/w/h이고 클래스 점수에는 이미 sigmoid가 적용돼 있다.
class YoloDecoder(
    private val labels: List<String>,
    private val candidateCount: Int = 8400,
    private val maskSize: Int = 160,
    private val maskChannels: Int = 32,
) {
    private data class Candidate(val index: Int, val label: Int, val score: Float, val box: List<Float>)

    fun decode(boxes: FloatArray, prototypes: FloatArray, width: Int, height: Int): List<Recognition> {
        require(boxes.size == (4 + labels.size + maskChannels) * candidateCount)
        require(prototypes.size == maskChannels * maskSize * maskSize)
        val gain = min(640f / width, 640f / height)
        val padX = (640 - width * gain) / 2
        val padY = (640 - height * gain) / 2
        val candidates = mutableListOf<Candidate>()

        for (i in 0 until candidateCount) {
            val label = labels.indices.maxBy { boxes[(4 + it) * candidateCount + i] }
            val score = boxes[(4 + label) * candidateCount + i]
            if (!score.isFinite() || score < 0.25f) continue

            val cx = boxes[i] * 640
            val cy = boxes[candidateCount + i] * 640
            val bw = boxes[2 * candidateCount + i] * 640
            val bh = boxes[3 * candidateCount + i] * 640
            val box = listOf(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
            if (box.any { !it.isFinite() } || bw <= 0 || bh <= 0) continue
            candidates += Candidate(i, label, score, box)
        }

        // 클래스별 NMS다. 지나친 후보는 잘라 분석 시간이 폭증하지 않게 한다.
        val kept = mutableListOf<Candidate>()
        for (candidate in candidates.sortedByDescending { it.score }.take(300)) {
            if (kept.none { it.label == candidate.label && iou(it.box, candidate.box) > 0.45f }) {
                kept += candidate
                if (kept.size == 30) break
            }
        }

        return kept.mapNotNull { candidate ->
            val box = candidate.box
            val restored = listOf(
                ((box[0] - padX) / gain).roundToInt().coerceIn(0, width - 1),
                ((box[1] - padY) / gain).roundToInt().coerceIn(0, height - 1),
                ((box[2] - padX) / gain).roundToInt().coerceIn(0, width - 1),
                ((box[3] - padY) / gain).roundToInt().coerceIn(0, height - 1),
            )
            if (restored[2] <= restored[0] || restored[3] <= restored[1]) return@mapNotNull null

            val name = labels[candidate.label]
            // 3번 판단에 필요한 점자블록 마스크만 다각형으로 복원한다.
            // 다른 클래스의 contour는 선택값 None으로 보내 불필요한 계산을 줄인다.
            val contour = if (name == "tactile_line" || name == "tactile_dot") {
                maskContour(candidate, boxes, prototypes, width, height, gain, padX, padY)
            } else null
            Recognition(candidate.index + 1, name, candidate.score, restored, contour)
        }
    }

    private fun iou(a: List<Float>, b: List<Float>): Float {
        val intersection = max(0f, min(a[2], b[2]) - max(a[0], b[0])) *
            max(0f, min(a[3], b[3]) - max(a[1], b[1]))
        val areaA = (a[2] - a[0]) * (a[3] - a[1])
        val areaB = (b[2] - b[0]) * (b[3] - b[1])
        return intersection / (areaA + areaB - intersection).coerceAtLeast(0.0001f)
    }

    private fun maskContour(
        candidate: Candidate, boxes: FloatArray, prototypes: FloatArray,
        width: Int, height: Int, gain: Float, padX: Float, padY: Float,
    ): List<List<Int>>? {
        val mask = BooleanArray(maskSize * maskSize)
        val step = 640f / maskSize
        val coefficients = FloatArray(maskChannels) {
            boxes[(4 + labels.size + it) * candidateCount + candidate.index]
        }

        // sigmoid(계수·prototype) > 0.5는 내적 > 0과 같다. bbox 밖은 잘라낸다.
        for (y in 0 until maskSize) for (x in 0 until maskSize) {
            val px = (x + 0.5f) * step
            val py = (y + 0.5f) * step
            if (px < candidate.box[0] || px > candidate.box[2] ||
                py < candidate.box[1] || py > candidate.box[3]) continue
            var value = 0f
            for (channel in 0 until maskChannels) {
                value += coefficients[channel] * prototypes[channel * mask.size + y * maskSize + x]
            }
            mask[y * maskSize + x] = value > 0
        }

        // 채워진 셀의 경계선을 이어 가장 큰 외곽선을 선택한다. 구멍은 외곽선에서 제외한다.
        val edges = mutableMapOf<Int, MutableList<Int>>()
        val stride = maskSize + 1
        fun filled(x: Int, y: Int) = x in 0 until maskSize && y in 0 until maskSize && mask[y * maskSize + x]
        fun edge(x1: Int, y1: Int, x2: Int, y2: Int) {
            edges.getOrPut(y1 * stride + x1) { mutableListOf() }.add(y2 * stride + x2)
        }
        for (y in 0 until maskSize) for (x in 0 until maskSize) if (filled(x, y)) {
            if (!filled(x, y - 1)) edge(x, y, x + 1, y)
            if (!filled(x + 1, y)) edge(x + 1, y, x + 1, y + 1)
            if (!filled(x, y + 1)) edge(x + 1, y + 1, x, y + 1)
            if (!filled(x - 1, y)) edge(x, y + 1, x, y)
        }
        var best = emptyList<Int>()
        var bestArea = 0L
        while (edges.isNotEmpty()) {
            val start = edges.keys.first()
            var current = start
            val loop = mutableListOf<Int>()
            do {
                loop += current
                val next = edges[current] ?: break
                val destination = next.removeAt(next.lastIndex)
                if (next.isEmpty()) edges.remove(current)
                current = destination
            } while (current != start)
            if (current != start || loop.size < 3) continue
            val area = abs(loop.indices.sumOf { i ->
                val a = loop[i]; val b = loop[(i + 1) % loop.size]
                (a % stride).toLong() * (b / stride) - (b % stride).toLong() * (a / stride)
            })
            if (area > bestArea) { bestArea = area; best = loop }
        }
        if (best.isEmpty()) return null

        // 일직선 중간 점은 제거한다. 픽셀 좌표로 되돌린 후 최대 128점으로 줄인다.
        val corners = best.indices.filter { i ->
            val a = best[(i + best.size - 1) % best.size]
            val b = best[i]
            val c = best[(i + 1) % best.size]
            (b % stride - a % stride) * (c / stride - b / stride) !=
                (b / stride - a / stride) * (c % stride - b % stride)
        }.map { best[it] }
        val sampling = ceil(corners.size / 128.0).toInt().coerceAtLeast(1)
        val points = corners.filterIndexed { index, _ -> index % sampling == 0 }.map {
            listOf(
                (((it % stride) * step - padX) / gain).roundToInt().coerceIn(0, width - 1),
                (((it / stride) * step - padY) / gain).roundToInt().coerceIn(0, height - 1),
            )
        }.distinct()
        return points.takeIf { it.size >= 3 }
    }
}
