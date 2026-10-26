package com.example.blindwalk.inference

import kotlin.math.*

/** 모델 출력 이후, 같은 분석 스레드에서 호출하는 세션 단위 추적기. */
class ObjectTracker {
    data class Diagnostics(
        val intervalMillis: Long? = null,
        val created: Int = 0,
        val reconnected: Int = 0,
        val expired: Int = 0,
        val evicted: Int = 0,
        val retained: Int = 0,
    )
    var diagnostics = Diagnostics()
        private set

    private data class Box(val x: Double, val y: Double, val w: Double, val h: Double) {
        val cx get() = x + w / 2
        val cy get() = y + h / 2
        val diagonal get() = hypot(w, h)
    }
    private data class Track(
        val id: Int, val className: String, val box: Box, val lastSeen: Long,
        val vx: Double = 0.0, val vy: Double = 0.0,
    )
    private data class Edge(val trackId: Int, val observation: Int, val cost: Double)

    private val tracks = linkedMapOf<Int, Track>()
    private var nextId = 1L
    private var lastUpdate: Long? = null

    fun update(observations: List<Recognition>, observedAtMillis: Long): List<Recognition> {
        val previousUpdate = lastUpdate
        require(observedAtMillis >= 0 && (previousUpdate == null || observedAtMillis >= previousUpdate))
        // 관측 선택 시각만 사용한다. 빈 탐지나 내부 예측은 lastSeen을 갱신하지 않는다.
        val expired = tracks.values.count { observedAtMillis - it.lastSeen > LOST_MILLIS }
        tracks.entries.removeAll { observedAtMillis - it.value.lastSeen > LOST_MILLIS }
        val boxes = observations.map { box(it.bbox) }
        val edges = mutableListOf<Edge>()
        for (track in tracks.values) for ((index, observation) in observations.withIndex()) {
            if (track.className != observation.className) continue
            val current = boxes[index] ?: continue
            cost(track, current, observedAtMillis)?.let { edges += Edge(track.id, index, it) }
        }

        val assignments = mutableMapOf<Int, Track>()
        val usedTracks = mutableSetOf<Int>()
        fun match(candidates: List<Edge>) {
            for (edge in candidates.sortedBy { it.cost }) {
                if (edge.trackId in usedTracks || edge.observation in assignments) continue
                // 다른 객체와 구별할 근거가 비슷하면 연결을 포기한다. 중복 할당도 막는다.
                val ambiguous = candidates.any { other ->
                    (other.trackId == edge.trackId && other.observation != edge.observation ||
                        other.observation == edge.observation && other.trackId != edge.trackId) &&
                        other.cost <= edge.cost + AMBIGUITY_MARGIN
                }
                if (!ambiguous) {
                    assignments[edge.observation] = tracks.getValue(edge.trackId)
                    usedTracks += edge.trackId
                }
            }
        }
        // 직전 관측의 연속성을 우선한다. 이전 유실 가설이 새 트랙과 끝없이 경쟁하지 않게 한다.
        val active = edges.filter { tracks.getValue(it.trackId).lastSeen == previousUpdate }
        match(active)
        val activeCandidates = active.map { it.observation }.toSet()
        // 활성 트랙과 모호했던 관측을 유실 트랙에 억지로 붙이지 않는다.
        match(edges.filter { it.observation !in activeCandidates })

        var created = 0
        var reconnected = 0
        val result = observations.mapIndexed { index, observation ->
            val previous = assignments[index]
            val id = previous?.id ?: run {
                // Int 계약을 넘으면 오류로 중단한다. 같은 세션에서 번호를 순환시키지 않는다.
                check(nextId <= Int.MAX_VALUE) { "추적 ID 범위를 초과했습니다" }
                created++
                (nextId++).toInt()
            }
            if (previous != null && previousUpdate != null && previous.lastSeen < previousUpdate) reconnected++
            boxes[index]?.let { current ->
                val seconds = if (previous == null) 0.0 else (observedAtMillis - previous.lastSeen) / 1000.0
                val vx = if (seconds > 0) (current.cx - previous!!.box.cx) / seconds else 0.0
                val vy = if (seconds > 0) (current.cy - previous!!.box.cy) / seconds else 0.0
                // 작은 시간 간격/검출 흔들림이 과도한 예측 이동을 만들지 않게 제한한다.
                val limit = current.diagonal * 2
                val scale = (limit / hypot(vx, vy).coerceAtLeast(1.0)).coerceAtMost(1.0)
                tracks[id] = Track(id, observation.className, current, observedAtMillis, vx * scale, vy * scale)
            }
            // 과거 bbox·contour·깊이는 복사하지 않는다. 현재 실제 관측의 ID만 바꾼다.
            observation.copy(id = id)
        }
        var evicted = 0
        while (tracks.size > MAX_TRACKS) {
            tracks.remove(tracks.values.minBy { it.lastSeen }.id)
            evicted++
        }
        diagnostics = Diagnostics(previousUpdate?.let { observedAtMillis - it }, created, reconnected,
            expired, evicted, tracks.size)
        lastUpdate = observedAtMillis
        return result
    }

    /** 세션 종료 때 분석 executor에서 호출한다. 다음 세션은 ID를 1부터 새로 시작한다. */
    fun reset() {
        tracks.clear()
        nextId = 1
        lastUpdate = null
        diagnostics = Diagnostics()
    }

    private fun box(values: List<Int>): Box? {
        if (values.size != 4) return null
        val w = values[2].toDouble() - values[0]
        val h = values[3].toDouble() - values[1]
        return if (w > 0 && h > 0) Box(values[0].toDouble(), values[1].toDouble(), w, h) else null
    }

    private fun cost(track: Track, current: Box, at: Long): Double? {
        val last = track.box
        val wr = current.w / last.w
        val hr = current.h / last.h
        if (wr !in 0.5..2.0 || hr !in 0.5..2.0) return null
        // 등속 예측은 내부 매칭에만 쓰며 500ms까지만 외삽한다. 크기는 예측하지 않는다.
        val dt = ((at - track.lastSeen) / 1000.0).coerceAtMost(0.5)
        val predicted = last.copy(x = last.x + track.vx * dt, y = last.y + track.vy * dt)
        val distance = hypot(current.cx - predicted.cx, current.cy - predicted.cy) /
            min(last.diagonal, current.diagonal)
        val intersection = max(0.0, min(predicted.x + predicted.w, current.x + current.w) - max(predicted.x, current.x)) *
            max(0.0, min(predicted.y + predicted.h, current.y + current.h) - max(predicted.y, current.y))
        val iou = intersection / (predicted.w * predicted.h + current.w * current.h - intersection)
        if (iou < 0.15 || distance > 0.65) return null
        return 0.65 * (1 - iou) + 0.25 * distance + 0.10 * (abs(ln(wr)) + abs(ln(hr)))
    }

    companion object {
        private const val LOST_MILLIS = 1_000L
        // 최대5FPS·프레임당30개라면 1000ms 경계 포함180개다. 전체 유실 구간을 보관한다.
        private const val MAX_TRACKS = 256
        private const val AMBIGUITY_MARGIN = 0.08
    }
}
