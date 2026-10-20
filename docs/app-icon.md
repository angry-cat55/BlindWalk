# BlindWalk 앱 아이콘

메인 화면의 보라색 BlindWalk 워드마크를 작은 아이콘에서도 읽을 수 있도록 Blind/Walk 두 줄로 배치했다.
흰 배경·투명 보라색 전경을 조합하고 원형/둥근 사각형 마스크에 맞는 여백을 둔다.

- 원본 전경: app/src/main/res/drawable-nodpi/blindwalk_wordmark.png
- 적응형 전경: app/src/main/res/drawable/ic_launcher_foreground.xml
- 적응형 아이콘: mipmap-anydpi-v26/ic_launcher.xml, ic_launcher_round.xml
- 구형 기기용: mipmap-mdpi~xxxhdpi의 ic_launcher.png, ic_launcher_round.png
- 제작: 내장 ImageGen. 생성 이미지의 영문 철자·두 줄 배치·투명 배경을 확인했고 런처 밀도별 크기로 패키징했다.

사용한 생성 프롬프트의 핵심 명세:
> Android adaptive launcher icon foreground, transparent square canvas. Exact text Blind on the first line and Walk on the second line. Bold clean Android-style sans serif, solid purple #6650A4. Center the two-line wordmark with generous transparent safe margins. No other symbols, shadows, gradients, phone frame or Android robot.

아이콘 리소스 빌드·lint는 통과했다. 무선 실기기가 offline이어서 새 아이콘의 런처 실제 표시는 미검증이다.
