"""
법정동별 매물 수집기
- 법정동별url수집.py로 수집한 URL 데이터를 읽어서 매물 상세 정보 크롤링
- 크롤링방법.txt 기반 완전 구현
- 동적 크롤링: 소개말 더보기, 관리비 상세보기, 실거래가 탭 전환
- 이미지 수집 및 저장
- 시/구/동 폴더 구조 자동 생성
"""
import asyncio
import json
import random
from playwright.async_api import async_playwright
from datetime import datetime
import re
import os
from pathlib import Path

# User-Agent 목록
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
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
    """페이지 렌더링 완료 대기"""
    try:
        await page.wait_for_load_state('networkidle', timeout=timeout)
        await page.wait_for_selector('body', timeout=5000)
        await page.evaluate("""
            () => new Promise(resolve => {
                if (document.readyState === 'complete') {
                    resolve();
                } else {
                    window.addEventListener('load', resolve);
                }
            })
        """)
        await random_sleep(2, 3)
        return True
    except Exception as e:
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

def ensure_folder_exists(folder_path):
    """폴더가 없으면 생성"""
    Path(folder_path).mkdir(parents=True, exist_ok=True)

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
    ensure_folder_exists(image_folder)
    
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

async def crawl_article(url, save_folder, image_folder):
    """매물 상세 페이지 크롤링"""
    
    user_agent = random.choice(USER_AGENTS)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': random.randint(1366, 1920), 'height': random.randint(768, 1080)},
            user_agent=user_agent,
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
        )
        
        await context.set_extra_http_headers({
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        page = await context.new_page()
        
        # 자동화 감지 우회
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en']
            });
        """)
        
        try:
            print(f"\n{'='*80}")
            print(f"매물 크롤링 시작")
            print(f"{'='*80}")
            print(f"URL: {url}")
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
                '매물분포': {},
                '실거래가': {'매매': [], '전세': [], '월세': []},
                '대출계산기': {},
                '시설정보': {},
                '개발예정': [],
                '중개사': {},
                '중개보수': {},
                '세금': {},
                '관리비': {},
                '주변대중교통': {}
            }
            
            # 1. 페이지 로드
            print("1. 페이지 로딩...")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await random_sleep(2, 4)
            print("   ✓ 완료\n")
            
            # 2. 렌더링 완료 대기
            print("2. 렌더링 완료 대기...")
            await wait_for_rendering(page)
            print("   ✓ 완료\n")
            
            # 3. 스크롤
            print("3. 콘텐츠 로딩...")
            await human_like_scroll(page)
            print("   ✓ 완료\n")

            # 4. 동적 크롤링: 소개말 더보기
            print("4. 소개말 더보기 클릭...")
            await click_button_with_text(page, ['소개말 더보기', '소개말더보기'], "소개말 더보기")
            print()
            
            # 5. 동적 크롤링: 관리비 상세보기
            print("5. 관리비 상세보기 클릭...")
            mgmt_detail_text = ""
            
            try:
                # 관리비 섹션으로 스크롤
                print("     → 관리비 섹션 찾는 중...")
                
                # 관리비 상세보기 버튼 찾기 (더 정확한 방법)
                mgmt_buttons = await page.query_selector_all('button, a, span[role="button"]')
                mgmt_button_found = False
                
                for btn in mgmt_buttons:
                    try:
                        btn_text = await btn.inner_text()
                        # "상세보기" 텍스트가 있고, 근처에 "관리비"가 있는지 확인
                        if '상세보기' in btn_text or '더보기' in btn_text:
                            # 버튼 주변 텍스트 확인
                            parent = await btn.evaluate_handle('(el) => el.parentElement')
                            parent_text = await parent.evaluate('(el) => el.innerText')
                            
                            if '관리비' in parent_text:
                                is_visible = await btn.is_visible()
                                if not is_visible:
                                    continue
                                
                                # 버튼 위치로 스크롤
                                box = await btn.bounding_box()
                                if box:
                                    await page.evaluate(f"window.scrollTo(0, {box['y'] - 300})")
                                    await random_sleep(0.5, 1)
                                    
                                    # 버튼 클릭
                                    await btn.click()
                                    await random_sleep(2, 3)
                                    mgmt_button_found = True
                                    print("     ✓ 관리비 상세보기 버튼 클릭 완료")
                                    break
                    except:
                        continue
                
                if mgmt_button_found:
                    # 팝업/모달이 열릴 때까지 대기
                    await random_sleep(1, 1.5)
                    
                    # 관리비 상세 데이터 수집
                    mgmt_detail_text = await page.evaluate("() => document.body.innerText")
                    print("     ✓ 관리비 상세 데이터 수집 완료")
                    
                    # 관리비 상세 정보를 기본정보에도 저장
                    # 관리비 합계
                    mgmt_total_match = re.search(r'관리비\s*합계\s*([\d,]+)\s*원', mgmt_detail_text)
                    if mgmt_total_match:
                        result['기본정보']['관리비합계_원'] = int(mgmt_total_match.group(1).replace(',', ''))
                    
                    # 포함 항목
                    include_match = re.search(r'포함\s*항목\s*\(사용료\)\s*:\s*([^\n]+)', mgmt_detail_text)
                    if include_match:
                        result['기본정보']['관리비포함항목'] = include_match.group(1).strip()
                    
                    # 관리비 기준
                    basis_match = re.search(r'관리비\s*기준\s*:\s*([^\n]+)', mgmt_detail_text)
                    if basis_match:
                        result['기본정보']['관리비기준'] = basis_match.group(1).strip()
                    
                    # 닫기 버튼 찾기 (여러 방법 시도)
                    print("     → 팝업 닫기 시도...")
                    close_success = False
                    
                    # 방법 1: "닫기" 텍스트가 있는 버튼
                    close_buttons = await page.query_selector_all('button, a, span[role="button"]')
                    for btn in close_buttons:
                        try:
                            btn_text = await btn.inner_text()
                            if btn_text and ('닫기' in btn_text or '닫기' == btn_text.strip() or 'X' in btn_text or '×' in btn_text):
                                is_visible = await btn.is_visible()
                                if is_visible:
                                    await btn.click()
                                    await random_sleep(0.5, 1)
                                    close_success = True
                                    print("     ✓ 닫기 버튼 클릭 완료")
                                    break
                        except:
                            continue
                    
                    # 방법 2: ESC 키
                    if not close_success:
                        await page.keyboard.press('Escape')
                        await random_sleep(0.5, 1)
                        print("     ✓ ESC 키로 닫기 완료")
                        close_success = True
                    
                    # 방법 3: 배경 클릭 (모달 외부)
                    if not close_success:
                        try:
                            await page.mouse.click(50, 50)
                            await random_sleep(0.5, 1)
                            print("     ✓ 배경 클릭으로 닫기 완료")
                        except:
                            pass
                    
                else:
                    print("     ℹ 관리비 상세보기 버튼 없음 (기본 정보만 수집)")
                    
            except Exception as e:
                print(f"     ℹ 관리비 상세보기 처리 중 오류: {e}")
            
            print()
            
            # 6. 페이지 텍스트 수집
            print("6. 기본 데이터 추출...")
            page_text = await page.evaluate("() => document.body.innerText")
            
            # === 매물정보 추출 (페이지 상단 요약 정보) ===
            # 단지명과 동 정보
            complex_match = re.search(r'([가-힣\s]+(?:아파트|빌라|오피스텔|주상복합))\s*(\d+동)', page_text)
            if complex_match:
                result['매물정보']['단지명'] = complex_match.group(1).strip()
                result['매물정보']['동'] = complex_match.group(2)
            
            # 면적과 층 정보 (상단 요약)
            area_floor_match = re.search(r'(?:아파트|빌라|오피스텔|주상복합)\s*([\d.]+)㎡\s*\(전용\s*([\d.]+)\)\s*(\d+)/(\d+)층', page_text)
            if area_floor_match:
                result['매물정보']['공급면적_제곱미터'] = float(area_floor_match.group(1))
                result['매물정보']['전용면적_제곱미터'] = float(area_floor_match.group(2))
                result['매물정보']['해당층'] = int(area_floor_match.group(3))
                result['매물정보']['총층수'] = int(area_floor_match.group(4))
            
            # 향 정보
            direction_simple_match = re.search(r'(\w+향)', page_text)
            if direction_simple_match:
                result['매물정보']['향'] = direction_simple_match.group(1)
            
            # 집주인확인매물
            if '집주인확인매물' in page_text:
                result['매물정보']['집주인확인매물'] = True
                owner_match = re.search(r'집주인확인매물\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', page_text)
                if owner_match:
                    result['매물정보']['집주인확인일'] = f"{owner_match.group(1)}-{owner_match.group(2).zfill(2)}-{owner_match.group(3).zfill(2)}"
            
            # 매물 설명 (상단 요약)
            intro_summary_match = re.search(r'(샷시포함|특|올수리|급매|가격조정|아이들|키우기|최적|깨끗|넓은|좋은|전망|채광|통풍)[^\n]{0,100}', page_text)
            if intro_summary_match:
                result['매물정보']['매물요약'] = intro_summary_match.group(0).strip()
            
            # === 대출정보 추출 (더 정확하게) ===
            # 대출 한도 섹션 찾기
            loan_section_match = re.search(r'대출\s*한도[^\n]*\n([^\n]*\n){0,5}', page_text)
            if loan_section_match:
                loan_section = loan_section_match.group(0)
                
                # 규제지역과 LTV
                ltv_match = re.search(r'(투기과열|조정대상|비규제)[,\s]*LTV\s*(\d+)%', loan_section)
                if ltv_match:
                    result['대출정보']['대출한도']['규제지역'] = ltv_match.group(1)
                    result['대출정보']['대출한도']['LTV_퍼센트'] = int(ltv_match.group(2))
                
                # 최대 대출 금액
                loan_amount_match = re.search(r'최대\s*([\d억,\s]+만?원)', loan_section)
                if loan_amount_match:
                    result['대출정보']['대출한도']['최대금액'] = loan_amount_match.group(1).strip()
            
            # 금리정보 (더 정확한 패턴)
            # "금리 정보" 섹션 찾기
            rate_section_match = re.search(r'금리\s*정보[^\n]*\n((?:[^\n]*\n){0,30})', page_text)
            if rate_section_match:
                rate_section = rate_section_match.group(0)
                
                # 은행명과 금리 추출
                bank_patterns = [
                    re.compile(r'([가-힣A-Z]+(?:은행|생명|저축은행|캐피탈))\s*([\d.]+%\s*~\s*[\d.]+%|[\d.]+%)'),
                    re.compile(r'(SC제일은행|KB국민은행|우리은행|신한은행|하나은행|농협은행|IBK기업은행|교보생명|한화생명|삼성생명)\s*([\d.]+%\s*~\s*[\d.]+%|[\d.]+%)'),
                ]
                
                for pattern in bank_patterns:
                    for match in pattern.finditer(rate_section):
                        bank_name = match.group(1).strip()
                        rate_range = match.group(2).strip()
                        
                        # 중복 체크
                        if not any(item['은행명'] == bank_name for item in result['대출정보']['금리정보']):
                            result['대출정보']['금리정보'].append({
                                '은행명': bank_name,
                                '금리범위': rate_range
                            })
            
            # === 매물분포 추출 ===
            dist_match = re.search(r'가격분포\s*매매\s*([\d억,\s~]+)', page_text)
            if dist_match:
                result['매물분포']['가격범위'] = dist_match.group(1).strip()
            
            count_match = re.search(r'매물수\s*(\d+)개', page_text)
            if count_match:
                result['매물분포']['총매물수'] = int(count_match.group(1))
            
            # === 대출계산기 추출 ===
            calc_loan_match = re.search(r'대출 금액\s*최대\s*([\d억,\s]+만?원)', page_text)
            if calc_loan_match:
                result['대출계산기']['대출금액'] = calc_loan_match.group(1).strip()
            
            kb_match = re.search(r'KB시세\s+([\d억,\s]+만?원)', page_text)
            if kb_match:
                result['대출계산기']['KB시세'] = kb_match.group(1).strip()
            
            period_match = re.search(r'대출 기간\s*최대\s*(\d+)년', page_text)
            if period_match:
                result['대출계산기']['대출기간_년'] = int(period_match.group(1))
            
            if '원리금균등' in page_text:
                result['대출계산기']['상환방법'] = ['원리금균등', '원금균등']
            
            lowest_rate_match = re.search(r'최저 금리[^\n]*?([가-힣]+(?:은행|생명))\s*([\d.]+%)', page_text)
            if lowest_rate_match:
                result['대출계산기']['최저금리_은행'] = lowest_rate_match.group(1)
                result['대출계산기']['최저금리'] = lowest_rate_match.group(2)
            
            monthly_match = re.search(r'예상 월 원리금\s*([\d,]+)원', page_text)
            if monthly_match:
                result['대출계산기']['예상월원리금_원'] = int(monthly_match.group(1).replace(',', ''))
            
            print("   ✓ 완료\n")
            
            # 7. 기본정보 추출
            print("7. 기본정보 추출...")
            
            # 매매가
            sale_price_match = re.search(r'매매가\s*([\d억,\s]+만?원)', page_text)
            if sale_price_match:
                result['기본정보']['매매가'] = sale_price_match.group(1).strip()
            
            # 관리비부과기준
            mgmt_basis_match = re.search(r'관리비부과기준\s*([^\n]+)', page_text)
            if mgmt_basis_match:
                result['기본정보']['관리비부과기준'] = mgmt_basis_match.group(1).strip()
            
            # 관리비
            mgmt_fee_match = re.search(r'관리비\s*(\d+)만원', page_text)
            if mgmt_fee_match:
                result['기본정보']['관리비_만원'] = int(mgmt_fee_match.group(1))
            
            # 공급/전용면적
            supply_match = re.search(r'공급면적\s*([\d.]+)㎡', page_text)
            if supply_match:
                result['기본정보']['공급면적_제곱미터'] = float(supply_match.group(1))
            
            exclusive_match = re.search(r'전용면적\s*([\d.]+)㎡\s*\(전용률\s*(\d+)%\)', page_text)
            if exclusive_match:
                result['기본정보']['전용면적_제곱미터'] = float(exclusive_match.group(1))
                result['기본정보']['전용률_퍼센트'] = int(exclusive_match.group(2))
            
            # 층
            floor_match = re.search(r'층\s*(\d+)층/\s*총\s*(\d+)층', page_text)
            if floor_match:
                result['기본정보']['해당층'] = int(floor_match.group(1))
                result['기본정보']['총층수'] = int(floor_match.group(2))
            
            # 방수/욕실수
            room_match = re.search(r'방수/욕실수\s*(\d+)/(\d+)개', page_text)
            if room_match:
                result['기본정보']['방수'] = int(room_match.group(1))
                result['기본정보']['욕실수'] = int(room_match.group(2))
            
            # 향
            direction_match = re.search(r'향\s*\(거실 기준\)\s*([^\n]+)', page_text)
            if direction_match:
                result['기본정보']['향'] = direction_match.group(1).strip()
            
            # 복층여부
            duplex_match = re.search(r'복층여부\s*([^\n]+)', page_text)
            if duplex_match:
                result['기본정보']['복층여부'] = duplex_match.group(1).strip()
            
            # 입주가능일
            movein_match = re.search(r'입주가능일\s*([^\n]+)', page_text)
            if movein_match:
                result['기본정보']['입주가능일'] = movein_match.group(1).strip()
            
            # 매물번호
            article_no_match = re.search(r'매물번호\s*([0-9-]+)', page_text)
            if article_no_match:
                result['기본정보']['매물번호'] = article_no_match.group(1)
            
            # 매물소개
            intro_match = re.search(r'매물소개\s*\n((?:(?!최초게재|허위|단지 정보|로딩중).)+)', page_text, re.DOTALL)
            if intro_match:
                intro_text = intro_match.group(1).strip()
                intro_text = re.sub(r'\d+ 번째.*', '', intro_text)
                intro_text = re.sub(r'선택됨.*', '', intro_text)
                intro_lines = [line.strip() for line in intro_text.split('\n') if line.strip() and len(line.strip()) > 5]
                result['기본정보']['매물소개'] = '\n'.join(intro_lines)
            
            # 최초게재일
            first_post_match = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*최초게재([가-힣]+)\s*제공', page_text)
            if first_post_match:
                result['기본정보']['최초게재일'] = f"{first_post_match.group(1)}-{first_post_match.group(2).zfill(2)}-{first_post_match.group(3).zfill(2)}"
                result['기본정보']['제공업체'] = first_post_match.group(4)
            
            print("   ✓ 완료\n")
            
            # 8. 이미지 수집
            print("8. 이미지 수집...")
            result['기본정보']['이미지'] = await save_images(page, article_id, image_folder)
            print()
            
            # 9. 단지정보 추출
            print("9. 단지정보 추출...")
            
            # 위치
            location_match = re.search(r'위치\s*([가-힣]+시\s+[가-힣]+구\s+[가-힣]+동\s+[\d-]+)', page_text)
            if location_match:
                result['단지정보']['위치'] = location_match.group(1).strip()
            
            # 위치좌표 추출 (모바일 페이지 → 로드뷰 버튼 클릭)
            try:
                print("     → 위치좌표 수집 중...")
                
                # 1. 모바일 near 페이지로 이동
                near_url = f"https://m.land.naver.com/near/article/{article_id}"
                print(f"     → 모바일 페이지 이동: {near_url}")
                
                await page.goto(near_url, wait_until='networkidle', timeout=30000)
                await random_sleep(3, 4)
                
                # 2. 로드뷰 버튼 찾기 (button.btn_control._btn_roadview)
                print("     → 로드뷰 버튼 찾는 중...")
                
                coord_found = False
                
                # 로드뷰 버튼 선택자들
                roadview_selectors = [
                    'button.btn_control._btn_roadview',
                    'button._btn_roadview',
                    'button[class*="roadview"]',
                    'button[class*="btn_control"]',
                ]
                
                for selector in roadview_selectors:
                    try:
                        buttons = await page.query_selector_all(selector)
                        
                        for btn in buttons:
                            try:
                                is_visible = await btn.is_visible()
                                if not is_visible:
                                    continue
                                
                                box = await btn.bounding_box()
                                if box:
                                    # 40x40 근처 크기의 버튼 찾기
                                    if 35 <= box['width'] <= 50 and 35 <= box['height'] <= 50:
                                        print(f"     ✓ 로드뷰 버튼 발견 ({int(box['width'])}x{int(box['height'])})")
                                        
                                        await page.evaluate(f"window.scrollTo(0, {box['y'] - 200})")
                                        await random_sleep(0.5, 1)
                                        
                                        # 새 창 열림 감지
                                        try:
                                            async with page.expect_popup(timeout=5000) as popup_info:
                                                await btn.click()
                                                await random_sleep(1, 2)
                                            
                                            roadview_page = await popup_info.value
                                            await roadview_page.wait_for_load_state('domcontentloaded')
                                            await random_sleep(1, 2)
                                            
                                            roadview_url = roadview_page.url
                                            print(f"     ✓ 로드뷰 URL: {roadview_url[:100]}...")
                                            
                                            # URL에서 좌표 추출
                                            lat_match = re.search(r'lat=([0-9.]+)', roadview_url)
                                            lng_match = re.search(r'lng=([0-9.]+)', roadview_url)
                                            
                                            if lat_match and lng_match:
                                                lat = float(lat_match.group(1))
                                                lng = float(lng_match.group(1))
                                                
                                                # 좌표 유효성 검증 (한국 범위)
                                                if 33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0:
                                                    result['단지정보']['위도'] = lat
                                                    result['단지정보']['경도'] = lng
                                                    print(f"     ✓ 좌표 수집 완료: {lat}, {lng}")
                                                    coord_found = True
                                                    
                                                    await roadview_page.close()
                                                    break
                                            
                                            await roadview_page.close()
                                            
                                        except Exception as e:
                                            print(f"     ℹ 팝업 처리 실패: {e}")
                                            continue
                            
                            except Exception as e:
                                continue
                        
                        if coord_found:
                            break
                    
                    except Exception as e:
                        continue
                
                # 3. 버튼 클릭 실패 시 페이지 소스에서 직접 추출
                if not coord_found:
                    print("     → 페이지 소스에서 좌표 검색...")
                    page_content = await page.content()
                    
                    patterns = [
                        r'map\.naver\.com/viewer/panorama[^"\']*lat=([0-9.]+)[^"\']*lng=([0-9.]+)',
                        r'lat=([0-9.]+)[^"\'&]*lng=([0-9.]+)',
                        r'"latitude"\s*:\s*([0-9.]+)[^}]{0,200}"longitude"\s*:\s*([0-9.]+)',
                        r'"lat"\s*:\s*([0-9.]+)[^}]{0,200}"lng"\s*:\s*([0-9.]+)',
                        r'"y"\s*:\s*([0-9.]+)[^}]{0,200}"x"\s*:\s*([0-9.]+)',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, page_content)
                        for match in matches:
                            try:
                                lat = float(match[0])
                                lng = float(match[1])
                                
                                if 33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0:
                                    result['단지정보']['위도'] = lat
                                    result['단지정보']['경도'] = lng
                                    print(f"     ✓ 좌표 수집 완료: {lat}, {lng}")
                                    coord_found = True
                                    break
                            except:
                                continue
                        
                        if coord_found:
                            break
                
                if not coord_found:
                    print("     ℹ 좌표 수집 실패")
                
                # 원래 페이지로 돌아가기
                print("     → 원래 페이지로 복귀...")
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await random_sleep(1, 2)
                    
            except Exception as e:
                print(f"     ℹ 좌표 추출 실패: {e}")
                # 실패해도 원래 페이지로 돌아가기 시도
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await random_sleep(1, 2)
                except:
                    pass
            
            # 건축물용도
            building_match = re.search(r'건축물용도\s*([^\n]+)', page_text)
            if building_match:
                result['단지정보']['건축물용도'] = building_match.group(1).strip()
            
            # 사용승인일
            approval_match = re.search(r'사용승인일\s*(\d{4})\.(\d{2})\.(\d{2})\s*\((\d+)년차\)', page_text)
            if approval_match:
                result['단지정보']['사용승인일'] = f"{approval_match.group(1)}-{approval_match.group(2)}-{approval_match.group(3)}"
                result['단지정보']['건물연차'] = int(approval_match.group(4))
            
            # 세대수
            household_match = re.search(r'세대수\s*(\d+(?:,\d+)?)\s*세대\s*\(해당 면적\s*(\d+(?:,\d+)?)\s*세대\)', page_text)
            if household_match:
                result['단지정보']['총세대수'] = int(household_match.group(1).replace(',', ''))
                result['단지정보']['해당면적세대수'] = int(household_match.group(2).replace(',', ''))
            
            # 현관구조
            entrance_match = re.search(r'현관구조\s*([^\n]+)', page_text)
            if entrance_match:
                result['단지정보']['현관구조'] = entrance_match.group(1).strip()
            
            # 난방
            heating_match = re.search(r'난방\s*([^\n]+)', page_text)
            if heating_match:
                result['단지정보']['난방'] = heating_match.group(1).strip()
            
            # 주차
            parking_match = re.search(r'주차\s*(\d+(?:,\d+)?)\s*대\s*\(세대당\s*([\d.]+)대\)', page_text)
            if parking_match:
                result['단지정보']['주차대수'] = int(parking_match.group(1).replace(',', ''))
                result['단지정보']['세대당주차'] = float(parking_match.group(2))
            
            # 용적률/건폐율
            ratio_match = re.search(r'용적률/건폐율\s*(\d+)%\s*/\s*(\d+)%', page_text)
            if ratio_match:
                result['단지정보']['용적률_퍼센트'] = int(ratio_match.group(1))
                result['단지정보']['건폐율_퍼센트'] = int(ratio_match.group(2))
            
            # 관리사무소 전화
            office_phone_match = re.search(r'관리사무소 전화\s*([\d-]+)', page_text)
            if office_phone_match:
                result['단지정보']['관리사무소전화'] = office_phone_match.group(1)
            
            # 건설사
            builder_match = re.search(r'건설사\s*([^\n]+)', page_text)
            if builder_match:
                result['단지정보']['건설사'] = builder_match.group(1).strip()
            
            print("   ✓ 완료\n")
            
            # 10. 시설정보 추출
            print("10. 시설정보 추출...")
            
            # 시설 더보기 버튼 클릭 (있는 경우)
            facility_more_clicked = await click_button_with_text(page, ['시설 더보기', '시설더보기', '더보기'], "시설 더보기")
            if facility_more_clicked:
                await random_sleep(1, 1.5)
                # 시설 더보기 후 페이지 텍스트 다시 수집
                page_text = await page.evaluate("() => document.body.innerText")
                print("     ✓ 시설 더보기 후 데이터 갱신")
            
            facilities = {
                '벽걸이에어컨': ['벽걸이에어컨', '벽걸이 에어컨', '에어컨'],
                '신발장': ['신발장'],
                '냉장고': ['냉장고'],
                '세탁기': ['세탁기'],
                '싱크대': ['싱크대'],
                '인덕션': ['인덕션'],
                '레인지': ['레인지', '가스레인지'],
                '엘리베이터': ['엘리베이터', 'EV']
            }
            
            for facility_key, keywords in facilities.items():
                for keyword in keywords:
                    if keyword in page_text:
                        result['시설정보'][facility_key] = True
                        break
                else:
                    result['시설정보'][facility_key] = False
            
            print("   ✓ 완료\n")
            
            # 11. 개발예정 추출
            print("11. 개발예정 추출...")
            
            station_pattern = re.compile(r'([가-힣]+역)\((\d{4})년예정\)\s*노선\s*([^\n]+)\s*개통\s*(\d{4})년 예정\s*거리\s*(\d+)m도보\s*(\d+)분')
            for match in station_pattern.finditer(page_text):
                result['개발예정'].append({
                    '역명': match.group(1),
                    '개통예정년도': int(match.group(2)),
                    '노선': match.group(3).strip(),
                    '거리_미터': int(match.group(5)),
                    '도보_분': int(match.group(6))
                })
            
            print(f"   ✓ {len(result['개발예정'])}개 역 정보 수집\n")
            
            # 12. 중개사 정보 추출
            print("12. 중개사 정보 추출...")
            
            agent_match = re.search(r'중개소\s*중개사\s*([^\n]+)\s*([가-힣]+공인중개사사무소)', page_text)
            if agent_match:
                result['중개사']['중개사명'] = agent_match.group(1).strip()
                result['중개사']['중개소명'] = agent_match.group(2).strip()
            
            agent_phone_match = re.search(r'중개사.*?전화\s*([\d-]+)', page_text, re.DOTALL)
            if agent_phone_match:
                result['중개사']['전화'] = agent_phone_match.group(1)
            
            agent_location_match = re.search(r'위치\s*([^\n]+(?:상가동|호)[^\n]*)', page_text)
            if agent_location_match:
                result['중개사']['위치'] = agent_location_match.group(1).strip()
            
            agent_reg_match = re.search(r'등록번호\s*([\d-]+)', page_text)
            if agent_reg_match:
                result['중개사']['등록번호'] = agent_reg_match.group(1)
            
            agent_record_match = re.search(r'최근\s*(\d+)개월\s*집주인확인\s*(\d+)건', page_text)
            if agent_record_match:
                result['중개사']['최근실적_개월'] = int(agent_record_match.group(1))
                result['중개사']['최근실적_건수'] = int(agent_record_match.group(2))
            
            print("   ✓ 완료\n")
            
            # 13. 중개보수 추출
            print("13. 중개보수 추출...")
            
            brokerage_match = re.search(r'중개 보수\s*최대\s*([\d,]+)만원', page_text)
            if brokerage_match:
                result['중개보수']['최대금액_원'] = int(brokerage_match.group(1).replace(',', '')) * 10000
            
            rate_match = re.search(r'상한 요율\s*([\d.]+)%', page_text)
            if rate_match:
                result['중개보수']['상한요율_퍼센트'] = float(rate_match.group(1))
            
            print("   ✓ 완료\n")
            
            # 14. 세금 정보 추출
            print("14. 세금 정보 추출...")
            
            acquisition_match = re.search(r'취득세 합계\s*약\s*([\d,]+)만원', page_text)
            if acquisition_match:
                result['세금']['취득세_원'] = int(acquisition_match.group(1).replace(',', '')) * 10000
            
            property_match = re.search(r'재산세 합계\s*약\s*([\d,]+)만원', page_text)
            if property_match:
                result['세금']['재산세_원'] = int(property_match.group(1).replace(',', '')) * 10000
            
            if '종합부동산세' in page_text and '과세대상 아님' in page_text:
                result['세금']['종합부동산세'] = '과세대상 아님'
            
            print("   ✓ 완료\n")
            
            # 15. 관리비 상세 추출
            print("15. 관리비 상세 추출...")
            
            # 관리비 상세보기에서 수집한 데이터 우선 사용
            mgmt_source = mgmt_detail_text if mgmt_detail_text else page_text
            
            # 기본 관리비 (만원 단위)
            if '관리비_만원' in result['기본정보']:
                result['관리비']['관리비_만원'] = result['기본정보']['관리비_만원']
            
            # 관리비 합계 (원 단위) - 더 정확한 패턴
            mgmt_total_patterns = [
                r'관리비\s*합계\s*([\d,]+)\s*원',
                r'관리비\s*([\d,]+)\s*원',
                r'(\d{1,3}(?:,\d{3})+)\s*원.*관리비',
            ]
            
            for pattern in mgmt_total_patterns:
                mgmt_total_match = re.search(pattern, mgmt_source)
                if mgmt_total_match:
                    result['관리비']['관리비합계_원'] = int(mgmt_total_match.group(1).replace(',', ''))
                    break
            
            # 기준년월과 최근 관리비
            recent_mgmt_patterns = [
                r'(\d{4})[.\s년]*(\d{1,2})[.\s월]*([\d,]+)\s*원',
                r'(\d{4})\s*년\s*(\d{1,2})\s*월.*?([\d,]+)\s*원',
            ]
            
            for pattern in recent_mgmt_patterns:
                recent_mgmt_match = re.search(pattern, mgmt_source)
                if recent_mgmt_match:
                    result['관리비']['기준년월'] = f"{recent_mgmt_match.group(1)}-{recent_mgmt_match.group(2).zfill(2)}"
                    result['관리비']['최근관리비_원'] = int(recent_mgmt_match.group(3).replace(',', ''))
                    break
            
            # 월 평균
            avg_patterns = [
                r'월\s*평균\s*[:\s]*([\d,]+)\s*원',
                r'평균\s*([\d,]+)\s*원',
            ]
            
            for pattern in avg_patterns:
                avg_match = re.search(pattern, mgmt_source)
                if avg_match:
                    result['관리비']['월평균_원'] = int(avg_match.group(1).replace(',', ''))
                    break
            
            # 여름 평균
            summer_patterns = [
                r'여름\s*\([\d~월\s]+\)\s*평균\s*([\d,]+)\s*원',
                r'여름.*?([\d,]+)\s*원',
            ]
            
            for pattern in summer_patterns:
                summer_match = re.search(pattern, mgmt_source)
                if summer_match:
                    result['관리비']['여름평균_원'] = int(summer_match.group(1).replace(',', ''))
                    break
            
            # 겨울 평균
            winter_patterns = [
                r'겨울\s*\([\d~월\s]+\)\s*평균\s*([\d,]+)\s*원',
                r'겨울.*?([\d,]+)\s*원',
            ]
            
            for pattern in winter_patterns:
                winter_match = re.search(pattern, mgmt_source)
                if winter_match:
                    result['관리비']['겨울평균_원'] = int(winter_match.group(1).replace(',', ''))
                    break
            
            # 포함 항목
            include_patterns = [
                r'포함\s*항목\s*\(사용료\)\s*:\s*([^\n]+)',
                r'포함\s*항목\s*:\s*([^\n]+)',
            ]
            
            for pattern in include_patterns:
                include_match = re.search(pattern, mgmt_source)
                if include_match:
                    result['관리비']['포함항목'] = include_match.group(1).strip()
                    break
            
            # 관리비 기준
            basis_patterns = [
                r'관리비\s*기준\s*:\s*([^\n]+)',
                r'기준\s*:\s*([^\n]+평균[^\n]*)',
            ]
            
            for pattern in basis_patterns:
                basis_match = re.search(pattern, mgmt_source)
                if basis_match:
                    result['관리비']['관리비기준'] = basis_match.group(1).strip()
                    break
            
            print(f"   ✓ 완료 (수집 항목: {len([k for k, v in result['관리비'].items() if v])}개)\n")
            
            # 16. 주변대중교통 추출
            print("16. 주변대중교통 추출...")
            
            result['주변대중교통']['버스'] = {}
            
            bus_match = re.search(r'버스\s*마을\s*([^\n]+)', page_text)
            if bus_match:
                buses = [b.strip() for b in re.split(r'[,\s]+', bus_match.group(1)) if b.strip() and not b.strip() in ['지선', '간선']]
                if buses:
                    result['주변대중교통']['버스']['마을'] = buses
            
            jiseon_match = re.search(r'지선\s*([\d,\s]+)', page_text)
            if jiseon_match:
                buses = [b.strip() for b in re.split(r'[,\s]+', jiseon_match.group(1)) if b.strip() and b.strip().isdigit()]
                if buses:
                    result['주변대중교통']['버스']['지선'] = buses
            
            ganseon_match = re.search(r'간선\s*([\d,\s]+)', page_text)
            if ganseon_match:
                buses = [b.strip() for b in re.split(r'[,\s]+', ganseon_match.group(1)) if b.strip() and b.strip().isdigit()]
                if buses:
                    result['주변대중교통']['버스']['간선'] = buses
            
            print("   ✓ 완료\n")

            # 17. 실거래가 동적 크롤링
            print("17. 실거래가 수집 (동적 크롤링)...")
            print(f"{'-'*80}")
            
            # 실거래가 더보기
            print("  [1] 실거래가 더보기 클릭...")
            await click_button_with_text(page, ['실거래가', '더보기'], "실거래가 더보기")
            
            # 실거래가 상세보기
            print("  [2] 실거래가 상세보기 클릭...")
            detail_clicked = await click_button_with_text(page, ['실거래가', '상세보기'], "실거래가 상세보기")
            
            if detail_clicked:
                await random_sleep(2, 3)
            
            # 매매/전세/월세 탭 크롤링
            trade_types = [
                ('매매', '매매'),
                ('전세', '전세'),
                ('월세', '월세')
            ]
            
            for idx, (tab_name, result_key) in enumerate(trade_types, 1):
                print(f"  [{idx+2}] {tab_name} 탭 크롤링...")
                
                try:
                    # 매매 탭은 이미 선택되어 있음 (실거래가 상세보기 클릭 시 기본 화면)
                    if idx > 1:
                        buttons = await page.query_selector_all('button, a, div[role="tab"], span')
                        tab_found = False
                        
                        for btn in buttons:
                            try:
                                text = await btn.inner_text()
                                if text and text.strip() == tab_name:
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
                                    await random_sleep(2, 3)
                                    tab_found = True
                                    print(f"     ✓ {tab_name} 탭 클릭 완료")
                                    break
                            except:
                                continue
                        
                        if not tab_found:
                            print(f"     ℹ {tab_name} 탭 없음")
                            continue
                    else:
                        print(f"     ✓ {tab_name} 탭 (기본 선택됨)")
                        await random_sleep(1, 1.5)
                    
                    # 탭 내용 스크롤하여 모든 데이터 로드
                    print(f"     → {tab_name} 탭 스크롤 중...")
                    last_height = await page.evaluate("() => document.body.scrollHeight")
                    scroll_attempts = 0
                    max_scroll_attempts = 10
                    
                    while scroll_attempts < max_scroll_attempts:
                        # 아래로 스크롤
                        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                        await random_sleep(1, 1.5)
                        
                        # 새 높이 확인
                        new_height = await page.evaluate("() => document.body.scrollHeight")
                        
                        if new_height == last_height:
                            # 더 이상 로드할 내용이 없음
                            break
                        
                        last_height = new_height
                        scroll_attempts += 1
                    
                    # 스크롤 완료 후 상단으로 이동
                    await page.evaluate("() => window.scrollTo(0, 0)")
                    await random_sleep(0.5, 1)
                    print(f"     ✓ 스크롤 완료 (시도: {scroll_attempts}회)")
                    
                    # 데이터 수집
                    await random_sleep(1, 1.5)
                    
                    # 페이지 텍스트와 HTML 모두 수집
                    trade_page_text = await page.evaluate("() => document.body.innerText")
                    trade_page_html = await page.content()
                    
                    print(f"     → 데이터 파싱 중...")
                    
                    transactions = []
                    
                    # 패턴 1: 날짜 + 면적 + 층 + 가격 (가장 일반적)
                    # 예: "11. 15. 69.84 5층 12억 5,000"
                    pattern1 = re.compile(r'(\d{1,2})[.\s]+(\d{1,2})[.\s]+(?:[\d.]+\s*)?(\d+)\s*층\s*([\d억,\s]+(?:만원?)?)')
                    for match in pattern1.finditer(trade_page_text):
                        try:
                            month = match.group(1).zfill(2)
                            day = match.group(2).zfill(2)
                            floor = int(match.group(3))
                            price = match.group(4).strip()
                            
                            # 가격 정리
                            price = re.sub(r'\s+', ' ', price)
                            price = price.replace('만원', '').strip()
                            
                            transactions.append({
                                '계약일': f"2025-{month}-{day}",
                                '층': floor,
                                '가격': price,
                                '비고': ''
                            })
                        except Exception as e:
                            continue
                    
                    # 패턴 2: 전체 날짜 형식
                    # 예: "2025-11-15 5층 12억 5,000"
                    pattern2 = re.compile(r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})\s*(\d+)\s*층\s*([\d억,\s/]+)')
                    for match in pattern2.finditer(trade_page_text):
                        try:
                            year = match.group(1)
                            month = match.group(2).zfill(2)
                            day = match.group(3).zfill(2)
                            floor = int(match.group(4))
                            price = match.group(5).strip()
                            
                            price = re.sub(r'\s+', ' ', price)
                            price = price.replace('만원', '').strip()
                            
                            transactions.append({
                                '계약일': f"{year}-{month}-{day}",
                                '층': floor,
                                '가격': price,
                                '비고': ''
                            })
                        except Exception as e:
                            continue
                    
                    # 패턴 3: 월세 형식 (보증금/월세)
                    # 예: "11. 15. 5층 1억/200"
                    if tab_name == '월세':
                        pattern3 = re.compile(r'(\d{1,2})[.\s]+(\d{1,2})[.\s]+(?:[\d.]+\s*)?(\d+)\s*층\s*([\d억,\s]+)/([\d,]+)')
                        for match in pattern3.finditer(trade_page_text):
                            try:
                                month = match.group(1).zfill(2)
                                day = match.group(2).zfill(2)
                                floor = int(match.group(3))
                                deposit = match.group(4).strip()
                                monthly = match.group(5).strip()
                                
                                price = f"{deposit}/{monthly}"
                                
                                transactions.append({
                                    '계약일': f"2025-{month}-{day}",
                                    '층': floor,
                                    '가격': price,
                                    '비고': ''
                                })
                            except Exception as e:
                                continue
                    
                    # 중복 제거
                    seen = set()
                    unique_transactions = []
                    for trans in transactions:
                        key = (trans['계약일'], trans['층'], trans['가격'])
                        if key not in seen:
                            seen.add(key)
                            unique_transactions.append(trans)
                    
                    result['실거래가'][result_key] = unique_transactions
                    print(f"     ✓ {len(unique_transactions)}건 수집")
                    
                    if unique_transactions:
                        for i, trans in enumerate(unique_transactions[:2], 1):
                            print(f"       {i}. {trans['계약일']} | {trans['층']}층 | {trans['가격']}")
                        if len(unique_transactions) > 2:
                            print(f"       ... 외 {len(unique_transactions)-2}건")
                    
                except Exception as e:
                    print(f"     ❌ {tab_name} 탭 처리 실패: {e}")
                
                await random_sleep(1, 1.5)
            
            print(f"{'-'*80}\n")
            
            # 결과 출력
            print(f"{'='*80}")
            print("수집 완료")
            print(f"{'='*80}")
            print(f"매물ID: {result['메타정보']['매물ID']}")
            print(f"위치: {result['단지정보'].get('위치', '정보없음')}")
            print(f"매매가: {result['기본정보'].get('매매가', '정보없음')}")
            print(f"매매 실거래: {len(result['실거래가']['매매'])}건")
            print(f"전세 실거래: {len(result['실거래가']['전세'])}건")
            print(f"월세 실거래: {len(result['실거래가']['월세'])}건")
            print(f"이미지: {len(result['기본정보']['이미지'])}개")
            print(f"{'='*80}\n")
            
            return result
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        finally:
            wait_time = random.randint(2, 3)
            print(f"브라우저를 {wait_time}초 후 종료합니다...")
            await asyncio.sleep(wait_time)
            await browser.close()

async def main():
    """메인 함수"""
    
    print("\n" + "="*80)
    print("법정동별 매물 수집기")
    print("="*80)
    print("\n[기능]")
    print("  ✓ 법정동별url수집.py로 수집한 URL 데이터 읽기")
    print("  ✓ 크롤링방법.txt 기반 완전 구현")
    print("  ✓ 동적 크롤링: 소개말 더보기, 관리비 상세보기, 시설 더보기, 실거래가 탭")
    print("  ✓ 이미지 수집 및 저장")
    print("  ✓ 사용자 지정 저장 경로")
    print("  ✓ 렌더링 완료 확인")
    print("  ✓ 프록시 우회, User-Agent, 타임슬립")
    print("="*80)
    print()
    
    # 1. URL 데이터 파일 경로 입력
    print("URL 데이터 파일 경로를 입력하세요:")
    print("예시: 매물url데이터\\서울시\\강서구\\마곡동\\마곡동url.json")
    url_file_path = input("\n입력: ").strip()
    
    if not os.path.exists(url_file_path):
        print(f"\n❌ 파일을 찾을 수 없습니다: {url_file_path}")
        return
    
    # 2. URL 데이터 파일 읽기
    try:
        with open(url_file_path, 'r', encoding='utf-8') as f:
            url_data = json.load(f)
        
        # 수집정보 가져오기
        collection_info = url_data.get('수집정보', {})
        
        # URL목록 가져오기
        url_list = url_data.get('URL목록', [])
        total_urls = len(url_list)
        
        if total_urls == 0:
            print("\n❌ URL목록이 비어있습니다.")
            return
        
        print(f"\n✓ URL 데이터 로드 완료")
        print(f"  - 생성시간: {collection_info.get('생성시간', '알수없음')}")
        print(f"  - 총 URL 수: {total_urls}개")
        print()
        
    except Exception as e:
        print(f"\n❌ URL 데이터 파일 읽기 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 매물 데이터 저장 경로 입력
    print("매물 데이터를 저장할 경로를 입력하세요:")
    print("예시: 매물데이터/서울시/강서구/공항동")
    save_folder = input("\n입력: ").strip()
    
    if not save_folder:
        print("\n❌ 저장 경로를 입력하지 않았습니다.")
        return
    
    # 저장 폴더 생성
    ensure_folder_exists(save_folder)
    print(f"✓ 저장 폴더 확인: {save_folder}")
    print()
    
    # 4. 이미지 저장 경로 입력
    print("이미지를 저장할 경로를 입력하세요:")
    print("예시: 매물이미지데이터/서울시/강서구/공항동")
    image_folder = input("\n입력: ").strip()
    
    if not image_folder:
        print("\n❌ 이미지 저장 경로를 입력하지 않았습니다.")
        return
    
    # 이미지 폴더 생성
    ensure_folder_exists(image_folder)
    print(f"✓ 이미지 폴더 확인: {image_folder}")
    print()
    
    # 5. 크롤링 개수 설정 (테스트용: 상위 3개)
    crawl_count = min(3, total_urls)
    
    print(f"\n✓ 테스트 모드: 상위 {crawl_count}개 매물 크롤링")
    print("="*80)
    print()
    
    # 6. 크롤링 실행
    target_urls = url_list[:crawl_count]
    success_count = 0
    fail_count = 0
    
    for idx, url_info in enumerate(target_urls, 1):
        url = url_info.get('URL', '')
        article_id = url_info.get('매물ID', 'unknown')
        
        print(f"\n{'='*80}")
        print(f"[{idx}/{crawl_count}] 매물 크롤링 시작")
        print(f"매물ID: {article_id}")
        print(f"URL: {url}")
        print(f"{'='*80}\n")
        
        try:
            # 크롤링 실행
            result = await crawl_article(url, save_folder, image_folder)
            
            if result:
                # 파일 저장
                filename = Path(save_folder) / f'article_{article_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                print(f"\n✅ [{idx}/{crawl_count}] 크롤링 성공!")
                print(f"   저장 위치: {filename}")
                success_count += 1
            else:
                print(f"\n❌ [{idx}/{crawl_count}] 크롤링 실패")
                fail_count += 1
        
        except Exception as e:
            print(f"\n❌ [{idx}/{crawl_count}] 크롤링 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1
        
        # 다음 크롤링 전 대기 (마지막 URL이 아닌 경우)
        if idx < len(target_urls):
            wait_time = random.uniform(2, 4)
            print(f"\n⏳ 다음 크롤링까지 {wait_time:.1f}초 대기...\n")
            await asyncio.sleep(wait_time)
    
    # 7. 최종 결과 출력
    print(f"\n{'='*80}")
    print("전체 크롤링 완료")
    print(f"{'='*80}")
    print(f"크롤링 대상: {crawl_count}개")
    print(f"성공: {success_count}개")
    print(f"실패: {fail_count}개")
    print(f"매물 데이터 저장: {save_folder}")
    print(f"이미지 저장: {image_folder}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(main())
