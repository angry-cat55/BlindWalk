package com.example.blindwalk.feedback

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.Intent
import android.hardware.usb.UsbManager
import android.os.Build
import com.example.blindwalk.inference.Recognition
import com.hoho.android.usbserial.driver.UsbSerialPort
import com.hoho.android.usbserial.driver.UsbSerialProber
import java.io.OutputStream
import java.util.UUID
import kotlin.concurrent.thread

@SuppressLint("MissingPermission")
class UsbHapticManager(private val context: Context) {
    private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    private var btSocket: BluetoothSocket? = null
    private var btOut: OutputStream? = null
    private var isBtConnecting = false
    private var lastBtAttemptTime = 0L

    private var serialPort: UsbSerialPort? = null
    private var lastPermissionRequestTime = 0L
    private var lastSentTime = 0L
    @Volatile private var pendingCmd: String = "C"

    fun connectIfNeeded() {
        if (btOut == null && !isBtConnecting && System.currentTimeMillis() - lastBtAttemptTime > 3000L) {
            lastBtAttemptTime = System.currentTimeMillis()
            try {
                val btManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
                val adapter = btManager?.adapter
                if (adapter != null && adapter.isEnabled) {
                    val targetDevice = adapter.bondedDevices?.firstOrNull {
                        it.name == "BlindWalk_Haptic" || it.name?.contains("ESP32") == true
                    }
                    if (targetDevice != null) {
                        isBtConnecting = true
                        thread {
                            try {
                                val socket = targetDevice.createRfcommSocketToServiceRecord(SPP_UUID)
                                socket.connect()
                                btSocket = socket
                                btOut = socket.outputStream
                            } catch (e: Exception) {
                                try { btSocket?.close() } catch (_: Exception) {}
                                btSocket = null
                                btOut = null
                            } finally {
                                isBtConnecting = false
                            }
                        }
                    }
                }
            } catch (_: Exception) {
                isBtConnecting = false
            }
        }

        if (serialPort != null) return
        val usbManager = context.getSystemService(Context.USB_SERVICE) as? UsbManager ?: return
        val availableDrivers = UsbSerialProber.getDefaultProber().findAllDrivers(usbManager)
        if (availableDrivers.isEmpty()) return

        val driver = availableDrivers[0]
        val device = driver.device

        if (!usbManager.hasPermission(device)) {
            val now = System.currentTimeMillis()
            if (now - lastPermissionRequestTime > 5000L) {
                lastPermissionRequestTime = now
                val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
                } else {
                    PendingIntent.FLAG_UPDATE_CURRENT
                }
                val intent = Intent("com.example.blindwalk.USB_PERMISSION").setPackage(context.packageName)
                val permissionIntent = PendingIntent.getBroadcast(context, 0, intent, flags)
                usbManager.requestPermission(device, permissionIntent)
            }
            return
        }

        val connection = usbManager.openDevice(device) ?: return
        try {
            serialPort = driver.ports[0].apply {
                open(connection)
                setParameters(115200, 8, UsbSerialPort.STOPBITS_1, UsbSerialPort.PARITY_NONE)
            }
        } catch (e: Exception) {
            serialPort = null
        }
    }

    fun vibrateForSelectedFeedback(selected: FeedbackResult, detections: List<Recognition>, frameWidth: Int = 640): String {
        // 시연 촬영을 위해 INFO(사람, 점자블록) 포함 모든 안내에서 좌/우/정면 햅틱 작동

        val targetObj = detections.firstOrNull { it.id == selected.objectId && it.bbox.size == 4 }
        val cmd = if (targetObj != null) {
            val centerX = (targetObj.bbox[0] + targetObj.bbox[2]) / 2f
            when {
                centerX < frameWidth / 3f -> "L"
                centerX > frameWidth * 2f / 3f -> "R"
                else -> "C"
            }
        } else {
            when {
                selected.message.contains("좌측") || selected.message.contains("왼쪽") -> "L"
                selected.message.contains("우측") || selected.message.contains("오른쪽") -> "R"
                else -> "C"
            }
        }

        pendingCmd = cmd
        sendRawCommand(cmd)
        return cmd
    }

    fun triggerPreparedPulse() {
        sendRawCommand(pendingCmd)
    }

    fun sendRawCommand(cmd: String) {
        val now = System.currentTimeMillis()
        if (now - lastSentTime < 200L) return
        connectIfNeeded()
        val data = cmd.toByteArray()

        val currentBtOut = btOut
        if (currentBtOut != null) {
            try {
                currentBtOut.write(data)
                currentBtOut.flush()
                lastSentTime = now
                return
            } catch (e: Exception) {
                try { btSocket?.close() } catch (_: Exception) {}
                btSocket = null
                btOut = null
            }
        }

        try {
            if (serialPort != null) {
                serialPort?.write(data, 50)
                lastSentTime = now
            }
        } catch (e: Exception) {
            try { serialPort?.close() } catch (_: Exception) {}
            serialPort = null
        }
    }

    fun close() {
        try { btSocket?.close() } catch (_: Exception) {}
        btSocket = null
        btOut = null
        try { serialPort?.close() } catch (_: Exception) {}
        serialPort = null
    }
}