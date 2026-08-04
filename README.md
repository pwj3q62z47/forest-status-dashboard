# 숲나들이 예약/대기 공개 대시보드 Render 배포

이 앱은 숲나들e 계정 정보 없이 공개용 예약/대기 현황만 보여줍니다.

## Render 설정

- Root Directory: `forest_status_dashboard_render`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python app.py`
- Environment Variable:
  - `UPLOAD_TOKEN`: 임의의 긴 문자열

배포 후 공개 주소 예:

`https://forest-status-dashboard.onrender.com`

## 로컬 PC 업로드 설정

`숲나들이_계정예약대기현황조회_Render업로드.bat` 파일에서 아래 값을 수정합니다.

```bat
set "FOREST_STATUS_UPLOAD_URL=https://forest-status-dashboard.onrender.com/api/upload"
set "FOREST_STATUS_UPLOAD_TOKEN=Render에 넣은 UPLOAD_TOKEN"
```

이후 배치 파일을 실행하면 계정별 예약/대기 현황을 조회한 뒤,
계정명/아이디 없이 공개용 데이터만 Render로 업로드합니다.

## 공개 화면에 포함되는 항목

- 예약/대기 구분
- 상태
- 이용기간
- D-Day
- 휴양림
- 객실
- 금액
- 비고

## 공개 화면에 포함하지 않는 항목

- 계정명
- 아이디
- 비밀번호
- 실행 로그
- 원본 파일 경로
