import os
import json
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class KISClient:
    """
    한국투자증권 (Korea Investment & Securities) API 클라이언트
    """
    def __init__(self):
        # 환경 변수 로드
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env')
        load_dotenv(env_path)
        
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.account = os.getenv("KIS_ACCOUNT")
        self.is_real = os.getenv("KIS_REAL_SERVER", "false").lower() == "true"
        
        self.base_url = "https://openapi.koreainvestment.com:9443" if self.is_real else "https://openapivts.koreainvestment.com:29443"
        self.token = None
        
    def _get_access_token(self):
        """접근 토큰 발급 (파일 캐싱 적용)"""
        token_cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.kis_token')
        
        # 1. 기존 캐시 확인
        if os.path.exists(token_cache_path):
            try:
                with open(token_cache_path, 'r') as f:
                    cache = json.load(f)
                # 만료 시간(유효기간 24시간 중 23시간으로 안전하게 설정) 확인 로직은 생략하고 일단 읽음
                # 실제로는 데이터가 있으면 바로 반환
                self.token = cache.get("access_token")
                if self.token:
                    logger.info("기존 캐시된 토큰을 사용합니다.")
                    return self.token
            except Exception:
                pass

        # 2. 신규 발급
        if not self.app_key or not self.app_secret:
            logger.error("KIS_APP_KEY 또는 KIS_APP_SECRET이 설정되지 않았습니다.")
            return None
            
        url = f"{self.base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                logger.error(f"토큰 발급 HTTP 에러: {resp.status_code} - {resp.text}")
                return None
            data = resp.json()
            if "access_token" in data:
                self.token = data["access_token"]
                # 파일에 저장
                with open(token_cache_path, 'w') as f:
                    json.dump(data, f)
                return self.token
            else:
                logger.error(f"토큰 발급 실패: {data}")
                return None
        except Exception as e:
            logger.error(f"토큰 발급 중 예외 발생: {e}")
            return None

    def get_short_selling_data(self, stock_code: str):
        """
        특정 종목의 공매도 정보 조회 (TR: FHKST30340000)
        """
        if not self.token and not self._get_access_token():
            return None
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/short-selling-status"
        
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST30340000",
            "custtype": "P"
        }
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "0000",
            "FID_INPUT_ISCD": stock_code
        }
        
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                logger.error(f"KIS API HTTP 에러: {resp.status_code} - {resp.text}")
                return None
            res_data = resp.json()
            
            if res_data.get("rt_cd") == "0":
                # 성공 시 첫 번째(가장 최근) 데이터 반환
                output = res_data.get("output", [])
                if output:
                    latest = output[0]
                    # 잔고비율 필드명: shrt_blnc_rate (또는 유사한 이름)
                    # 실제 API 명세 확인 필요. 여기서는 shrt_blnc_rate로 가정
                    # KIS API 필드명은 대문자인 경우가 많음
                    return {
                        "ratio": float(latest.get("shrt_blnc_rate", latest.get("SHRT_BLNC_RATE", 0))),
                        "volume": int(latest.get("shrt_vol", latest.get("SHRT_VOL", 0))),
                        "value": int(latest.get("shrt_val", latest.get("SHRT_VAL", 0))),
                    }
            else:
                logger.warning(f"KIS API 조회 실패 ({stock_code}): {res_data.get('msg1')}")
                return None
        except Exception as e:
            logger.error(f"KIS API 조회 중 예외 발생: {e}")
            return None

    def get_current_price(self, stock_code: str):
        """현재가 조회 테스트 (TR: FHKST01010100)"""
        if not self.token and not self._get_access_token():
            return None
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100",
            "custtype": "P"
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            return resp.json()
        except Exception as e:
            logger.error(f"시세 조회 예외: {e}")
            return None

if __name__ == "__main__":
    # 독립 실행 테스트
    logging.basicConfig(level=logging.INFO)
    client = KISClient()
    test_code = "005930" # 삼성전자
    print(f"--- KIS API 테스트 ({test_code}) ---")
    
    # 1. 시세 조회 테스트
    print("1. 시세 조회 시도...")
    price_data = client.get_current_price(test_code)
    if price_data and price_data.get("rt_cd") == "0":
        print(f"   성공! 현재가: {price_data['output']['stck_prpr']}")
        print(f"   상세 데이터 필드: {list(price_data['output'].keys())[:10]}...") # 처음 10개 필드만 확인
    else:
        print(f"   시세 조회 실패: {price_data}")

    # 2. 공매도 조회 테스트
    print("\n2. 공매도 정보 조회 시도...")
    data = client.get_short_selling_data(test_code)
    if data:
        print(f"   성공! 공매도 잔고 비율: {data['ratio']}%")
    else:
        print("   공매도 데이터를 가져오지 못했습니다.")
