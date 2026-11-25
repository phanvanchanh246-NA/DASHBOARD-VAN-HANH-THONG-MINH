# App Android "GHN Dashboard"

App mở thẳng dashboard trên Render, hiển thị toàn màn hình:
- có icon GHN và màn hình chờ;
- giữ đăng nhập giữa các lần mở app;
- nút Quay lại hoạt động như trên trình duyệt;
- tải ảnh hoặc file từ dashboard về thư mục Download;
- link Google Sheet, Telegram… mở bằng app ngoài;
- báo "Không kết nối được" kèm nút **Thử lại** khi mất mạng.

Mọi số liệu và tính năng đều nằm ở dashboard. Khi sửa `app.py` và deploy Render, app tự có bản mới, **không cần cài lại**. Chỉ build lại APK khi đổi địa chỉ dashboard, icon hoặc tên app.

## Build APK

Cần JDK 17+ và Android SDK. Không cần Android Studio hay Gradle.

```bash
sdkmanager "platforms;android-34" "build-tools;34.0.0" "cmdline-tools;latest"
ANDROID_SDK=/duong/dan/android-sdk KEYSTORE=/duong/dan/ghn-dashboard.keystore KEY_PASS='mat-khau' \
  ./android/build.sh https://ten-app.onrender.com 2 1.1
```

Ba tham số theo thứ tự:
- địa chỉ dashboard;
- `versionCode`: số nguyên, phải tăng mỗi lần phát hành bản mới;
- `versionName`: tên phiên bản hiển thị.

File ra nằm ở `android/build/GHN-Dashboard-<versionName>.apk`.

**Giữ kỹ file khoá `KEYSTORE` và mật khẩu.** Bản cập nhật phải ký bằng đúng khoá cũ thì điện thoại mới cho cài đè. Không đưa file khoá lên GitHub (đã chặn trong `.gitignore`).

## Cài lên điện thoại Android

1. Gửi file `.apk` qua Zalo, Telegram hoặc Google Drive.
2. Mở file trên điện thoại.
3. Nếu máy hỏi, cho phép **"Cài ứng dụng không rõ nguồn gốc"** với app đang dùng để mở file (Zalo, Files…).
4. Bấm **Cài đặt**. Biểu tượng **GHN Dashboard** sẽ xuất hiện trên màn hình chính.

iPhone không cài được file APK. Trên iPhone, dùng Safari → **Chia sẻ** → **Thêm vào MH chính**.
