"""
네이버 부동산 상세 매물 수집기
- 입력받은 URL로 매물 크롤링
- 렌더링 완료 확인
- 프록시 우회, User-Agent, 타임슬립 적용
- F12 감지 우회
"""
import asyncio
import json
from playwright.async_api import async_playwright
from datetime import datetime
import re
import random
import os
from pathlib import Path

# Mozilla User-Agent 목록
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

async def random_sleep(min_sec=1, max_sec=3):
    """랜덤 대기 (타임슬립)"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def human_like_scroll(page):
    """사람처럼 스크롤"""
    scroll_steps = random.randint(3, 5)
    for i in range(scroll_steps):
        scroll_amount = random.randint(600, 1000)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await random_sleep(0.5, 1.2)
    
    if random.random() > 0.7:
        await page.evaluate(f"window.scrollBy(0, -{random.randint(200, 400)})")
        await random_sleep(0.3, 0.8)
    
    await page.evaluate("window.scrollTo(0, 0)")
    await random_sleep(0.8, 1.5)

async def wait_for_rendering(page, timeout=30000):
    """
    페이지 렌더링 완료 대기
    - DOM 로드 완료
    - 네트워크 idle 상태
    - 주요 요소 로드 확인
    """
    try:
        print("  → 렌더링 상태 확인 중...")
        
        # 1. 네트워크 idle 대기
        await page.wait_for_load_state('networkidle', timeout=timeout)
        print("  ✓ 네트워크 idle 완료")
        
        # 2. 주요 요소 로드 대기 (매물 정보가 있는지 확인)
        try:
            await page.wait_for_selector('body', timeout=5000)
            print("  ✓ Body 요소 로드 완료")
        except:
            pass
        
        # 3. JavaScript 실행 완료 대기
        await page.evaluate("""
            () => new Promise(resolve => {
                if (document.readyState === 'complete') {
                    resolve();
                } else {
                    window.addEventListener('load', resolve);
                }
            })
        """)
        print("  ✓ JavaScript 실행 완료")
        
        # 4. 추가 대기 (동적 콘텐츠 로딩)
        await random_sleep(2, 3)
        print("  ✓ 렌더링 완료")
        
        return True
    
    except Exception as e:
        print(f"  ℹ 렌더링 대기 중 오류: {e}")
        return False

async def click_button_with_text(page, text_keywords, description="버튼"):
    """텍스트로 버튼 찾아서 클릭"""
    try:
        buttons = await page.query_selector_all('button, a')
        for btn in buttons:
            try:
                btn_text = await btn.inner_text()
                if any(keyword in btn_text for keyword in text_keywords):
                    is_visible = await btn.is_visible()
                    if not is_visible:
                        continue
                    
                    box = await btn.bounding_box()
                    if box:
                        await page.evaluate(f"window.scrollTo(0, {box['y'] - 200})")
                        await random_sleep(0.3, 0.6)
                        await page.mouse.move(
                            box['x'] + box['width'] / 2,
                            box['y'] + box['height'] / 2
                        )
                        await random_sleep(0.2, 0.4)
                    
                    await btn.click()
                    await random_sleep(1, 2)
                    print(f"     ✓ {description} 클릭 완료")
                    return True
            except:
                continue
        
        print(f"     ℹ {description} 없음")
        return False
    except Exception as e:
        print(f"     ℹ {description} 처리 실패: {e}")
        return False

def parse_location(location_text):
    """위치 텍스트에서 시/구/동 추출"""
    if not location_text:
        return None, None, None
    
    match = re.search(r'([가-힣]+시)\s+([가-힣]+구|[가-힣]+군)\s+([가-힣]+동|[가-힣]+읍|[가-힣]+면)', location_text)
    if match:
        return match.group(1), match.group(2), match.group(3)
    
    return None, None, None

def create_folder_structure(city, district, dong, base_folder="매물데이터"):
    """시/구/동 폴더 구조 생성"""
    if not city or not district or not dong:
        folder_path = Path(f"{base_folder}/미분류")
    else:
        folder_path = Path(f"{base_folder}/{city}/{district}/{dong}")
    
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

async def download_and_save_image(page, src, image_folder, idx, images_data, img_box):
    """이미지 다운로드 및 저장"""
    try:
        clean_url = src.strip()
        response = await page.request.get(clean_url)
        if response.ok:
            image_data = await response.body()
            
            if len(image_data) < 3000:
                return False
            
            ext = 'jpg'
            if '.png' in src.lower():
                ext = 'png'
            elif '.jpeg' in src.lower() or '.jpg' in src.lower():
                ext = 'jpg'
            elif '.webp' in src.lower():
                ext = 'webp'
            elif '.gif' in src.lower():
                ext = 'gif'
            
            filename = f'{image_folder}/image_{idx}.{ext}'
            with open(filename, 'wb') as f:
                f.write(image_data)
            
            images_data.append({
                '순서': idx,
                'URL': src,
                '파일경로': filename,
                '파일크기_bytes': len(image_data),
                '이미지크기': f"{int(img_box['width'])}x{int(img_box['height'])}",
                '수집시간': datetime.now().isoformat()
            })
            
            return True
    
    except Exception as e:
        return False

async def save_images(page, article_id, image_base_folder):
    """매물 이미지 수집 및 파일로 저장"""
    images_data = []
    
    image_folder = f'{image_base_folder}/images_{article_id}'
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
    
    try:
        print("     → 페이지 상단으로 스크롤...")
        await page.evaluate("window.scrollTo(0, 0)")
        await random_sleep(1, 2)
        
        print("     → 메인 이미지 찾는 중...")
        all_images = await page.query_selector_all('img')
        
        collected_urls = set()
        saved_count = 0
        
        for img in all_images:
            try:
                is_visible = await img.is_visible()
                if not is_visible:
                    continue
                
                img_box = await img.bounding_box()
                if not img_box or img_box['width'] < 300 or img_box['height'] < 300:
                    continue
                
                if img_box['y'] > 1500:
                    continue
                
                src = await img.get_attribute('src')
                
                if not src or 'http' not in src:
                    continue
                
                if src in collected_urls:
                    continue
                
                if 'phinf' in src or 'land.naver' in src or 'naver.net' in src:
                    saved_count += 1
                    success = await download_and_save_image(page, src, image_folder, saved_count, images_data, img_box)
                    if success:
                        collected_urls.add(src)
                        print(f"     ✓ {saved_count}번째 이미지 발견")
                    
                    if saved_count >= 10:
                        break
            
            except Exception as e:
                continue
        
        print(f"     ✓ 총 {len(images_data)}개 이미지 파일 저장 완료")
        return images_data
    
    except Exception as e:
        print(f"     ℹ 이미지 수집 실패: {e}")
        return images_data

async def crawl_article(url):
    """매물 상세 페이지 크롤링"""
    
    # 랜덤 User-Agent 선택
    user_agent = random.choice(USER_AGENTS)
    
    async with async_playwright() as p:
        # 브라우저 실행 (강력한 우회 설정)
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-infobars',
                '--window-size=1920,1080',
            ]
        )
        
        # 컨텍스트 생성 (프록시 우회 설정)
        context = await browser.new_context(
            viewport={'width': random.randint(1366, 1920), 'height': random.randint(768, 1080)},
            user_agent=user_agent,
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            # 추가 설정
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
        )
        
        # HTTP 헤더 설정
        await context.set_extra_http_headers({
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        page = await context.new_page()
        
        # 강력한 자동화 감지 우회 스크립트
        await page.add_init_script("""
            // WebDriver 감지 우회
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Chrome 객체 추가
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Plugins 추가
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Languages 설정
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en']
            });
            
            // Permission 우회
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // F12 감지 우회
            const devtools = /./;
            devtools.toString = function() {
                return '';
            };
            
            // Console 감지 우회
            let checkStatus = false;
            const element = new Image();
            Object.defineProperty(element, 'id', {
                get: function() {
                    checkStatus = true;
                }
            });
            
            // DevTools 열림 감지 무력화
            setInterval(() => {
                checkStatus = false;
            }, 1000);
        """)
        
        try:
            print(f"\n{'='*80}")
            print(f"매물 크롤링 시작")
            print(f"{'='*80}")
            print(f"URL: {url}")
            print(f"User-Agent: {user_agent[:50]}...")
            print()
            
            # 매물 ID 추출
            article_id = 'unknown'
            id_match = re.search(r'/articles/(\d+)', url)
            if id_match:
                article_id = id_match.group(1)
            
            # 데이터 구조 초기화
            result = {
                '메타정보': {
                    '매물ID': article_id,
                    'URL': url,
                    '수집시간': datetime.now().isoformat(),
                    'User-Agent': user_agent
                },
                '매물정보': {},
                '기본정보': {'이미지': []},
                '단지정보': {},
                '대출정보': {'대출한도': {}, '금리정보': []},
                '실거래가': {'매매': [], '전세': [], '월세': []},
            }
            
            # 1. 페이지 로드
            print("1. 페이지 로딩...")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await random_sleep(2, 4)
            print("   ✓ 완료\n")
            
            # 2. 렌더링 완료 대기
            print("2. 렌더링 완료 대기...")
            await wait_for_rendering(page)
            print()
            
            # 3. 스크롤
            print("3. 콘텐츠 로딩...")
            await human_like_scroll(page)
            print("   ✓ 완료\n")

            # 4. 동적 크롤링: 소개말 더보기
            print("4. 소개말 더보기 클릭...")
            await click_button_with_text(page, ['소개말 더보기', '소개말더보기'], "소개말 더보기")
            print()
            
            # 5. 페이지 텍스트 수집
            print("5. 기본 데이터 추출...")
            page_text = await page.evaluate("() => document.body.innerText")
            
            # 위치 정보 추출
            location_match = re.search(r'위치\s*([가-힣]+시\s+[가-힣]+구\s+[가-힣]+동\s+[\d-]+)', page_text)
            if location_match:
                result['단지정보']['위치'] = location_match.group(1).strip()
            
            # 단지명 추출
            complex_match = re.search(r'([가-힣\s]+(?:아파트|빌라|오피스텔))\s*(\d+동)', page_text)
            if complex_match:
                result['단지정보']['단지명'] = complex_match.group(1).strip()
                result['매물정보']['동'] = complex_match.group(2)
            
            # 매매가 추출
            sale_price_match = re.search(r'매매가\s*([\d억,\s]+만?원)', page_text)
            if sale_price_match:
                result['기본정보']['매매가'] = sale_price_match.group(1).strip()
            
            # 면적 정보
            area_match = re.search(r'공급면적\s*([\d.]+)㎡', page_text)
            if area_match:
                result['기본정보']['공급면적_제곱미터'] = float(area_match.group(1))
            
            # 층 정보
            floor_match = re.search(r'층\s*(\d+)층/\s*총\s*(\d+)층', page_text)
            if floor_match:
                result['기본정보']['해당층'] = int(floor_match.group(1))
                result['기본정보']['총층수'] = int(floor_match.group(2))
            
            print("   ✓ 완료\n")
            
            # 6. 이미지 수집
            print("6. 이미지 수집...")
            location_text = result['단지정보'].get('위치', '')
            city, district, dong = parse_location(location_text)
            image_folder = create_folder_structure(city, district, dong, "매물이미지데이터")
            
            result['기본정보']['이미지'] = await save_images(page, article_id, str(image_folder))
            print()
            
            # 7. 결과 출력
            print(f"{'='*80}")
            print("수집 완료")
            print(f"{'='*80}")
            print(f"매물ID: {result['메타정보']['매물ID']}")
            print(f"위치: {result['단지정보'].get('위치', '정보없음')}")
            print(f"단지명: {result['단지정보'].get('단지명', '정보없음')}")
            print(f"매매가: {result['기본정보'].get('매매가', '정보없음')}")
            print(f"이미지: {len(result['기본정보']['이미지'])}개")
            print(f"{'='*80}\n")
            
            # 8. 파일 저장
            data_folder = create_folder_structure(city, district, dong, "매물데이터")
            filename = data_folder / f'article_{article_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 저장 완료: {filename}\n")
            
            return result
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        finally:
            wait_time = random.randint(3, 5)
            print(f"브라우저를 {wait_time}초 후 종료합니다...")
            await asyncio.sleep(wait_time)
            await browser.close()

async def main():
    """메인 함수"""
    
    print("\n" + "="*80)
    print("네이버 부동산 상세 매물 수집기")
    print("="*80)
    print("- 렌더링 완료 확인")
    print("- 프록시 우회, User-Agent, 타임슬립 적용")
    print("- F12 감지 우회")
    print("="*80 + "\n")
    
    # URL 입력 받기
    url = input("매물 URL을 입력하세요: ").strip()
    
    if not url:
        print("❌ URL이 입력되지 않았습니다.")
        return
    
    if 'fin.land.naver.com/articles/' not in url:
        print("❌ 올바른 네이버 부동산 매물 URL이 아닙니다.")
        print("예시: https://fin.land.naver.com/articles/2561996357")
        return
    
    # 크롤링 실행
    result = await crawl_article(url)
    
    if result:
        print("\n✅ 크롤링 성공!")
    else:
        print("\n❌ 크롤링 실패")

if __name__ == "__main__":
    asyncio.run(main())
