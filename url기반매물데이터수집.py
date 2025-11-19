"""
네이버 부동산 매물 상세 페이지 크롤러 v3
크롤링방법.txt 기반 완전 재구성 버전
- 컬럼 구조 재정리
- 동적 크롤링 순서 명확화
- 이미지 수집 기능 추가
"""
import asyncio
import json
import base64
from playwright.async_api import async_playwright
from datetime import datetime
import re
import random
import os

# User-Agent 목록
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

async def random_sleep(min_sec=1, max_sec=3):
    """랜덤 대기"""
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

async def save_images(page, article_id):
    """매물 이미지 수집 및 파일로 저장 (개선 버전)"""
    images_data = []
    
    # 이미지 저장 폴더 생성
    image_folder = f'images_{article_id}'
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)
    
    try:
        print("     → 페이지 상단으로 스크롤...")
        await page.evaluate("window.scrollTo(0, 0)")
        await random_sleep(1, 2)
        
        # 방법 1: 페이지 상단의 큰 이미지들 수집 (메인 이미지 갤러리)
        print("     → 메인 이미지 찾는 중...")
        all_images = await page.query_selector_all('img')
        
        collected_urls = set()
        saved_count = 0
        
        for img in all_images:
            try:
                # 이미지가 보이는지 확인
                is_visible = await img.is_visible()
                if not is_visible:
                    continue
                
                img_box = await img.bounding_box()
                # 큰 이미지만 수집 (최소 300x300)
                if not img_box or img_box['width'] < 300 or img_box['height'] < 300:
                    continue
                
                # 페이지 상단 영역의 이미지만 (Y 좌표 < 1500)
                if img_box['y'] > 1500:
                    continue
                
                src = await img.get_attribute('src')
                
                # 유효한 이미지 URL인지 확인
                if not src or 'http' not in src:
                    continue
                
                # 이미 수집한 URL은 스킵
                if src in collected_urls:
                    continue
                
                # 네이버 부동산 이미지인지 확인
                if 'phinf' in src or 'land.naver' in src or 'naver.net' in src:
                    saved_count += 1
                    success = await download_and_save_image(page, src, image_folder, saved_count, images_data, img_box)
                    if success:
                        collected_urls.add(src)
                        print(f"     ✓ {saved_count}번째 이미지 발견 ({int(img_box['width'])}x{int(img_box['height'])})")
                    
                    # 최대 10개까지만 수집
                    if saved_count >= 10:
                        break
            
            except Exception as e:
                continue
        
        # 방법 2: 이미지가 없으면 페이지 소스에서 이미지 URL 추출
        if len(images_data) == 0:
            print("     → 페이지 소스에서 이미지 URL 추출 시도...")
            page_content = await page.content()
            
            # 이미지 URL 패턴 찾기
            image_url_patterns = [
                r'https://[^"\']+phinf[^"\']+\.(?:jpg|jpeg|png|webp)',
                r'https://[^"\']+land\.naver[^"\']+\.(?:jpg|jpeg|png|webp)',
                r'https://[^"\']+naver\.net[^"\']+\.(?:jpg|jpeg|png|webp)'
            ]
            
            for pattern in image_url_patterns:
                urls = re.findall(pattern, page_content)
                for url in urls:
                    if url not in collected_urls:
                        saved_count += 1
                        # 임시 박스 정보
                        temp_box = {'width': 800, 'height': 600}
                        success = await download_and_save_image(page, url, image_folder, saved_count, images_data, temp_box)
                        if success:
                            collected_urls.add(url)
                            print(f"     ✓ {saved_count}번째 이미지 URL 추출")
                        
                        if saved_count >= 10:
                            break
                
                if saved_count >= 10:
                    break
        
        print(f"     ✓ 총 {len(images_data)}개 이미지 파일 저장 완료")
        return images_data
    
    except Exception as e:
        print(f"     ℹ 이미지 수집 실패: {e}")
        import traceback
        traceback.print_exc()
        return images_data



async def download_and_save_image(page, src, image_folder, idx, images_data, img_box):
    """이미지 다운로드 및 저장"""
    try:
        # URL 정리 (쿼리 파라미터 제거하지 않음)
        clean_url = src.strip()
        
        response = await page.request.get(clean_url)
        if response.ok:
            image_data = await response.body()
            
            # 파일 크기 확인 (최소 3KB)
            if len(image_data) < 3000:
                return False
            
            # 파일 확장자 추출
            ext = 'jpg'
            if '.png' in src.lower():
                ext = 'png'
            elif '.jpeg' in src.lower() or '.jpg' in src.lower():
                ext = 'jpg'
            elif '.webp' in src.lower():
                ext = 'webp'
            elif '.gif' in src.lower():
                ext = 'gif'
            
            # 파일 저장
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
        # 에러 무시하고 계속 진행
        return False

async def crawl_article(url):
    """매물 상세 페이지 크롤링"""
    
    user_agent = random.choice(USER_AGENTS)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': random.randint(1366, 1920), 'height': random.randint(768, 1080)},
            user_agent=user_agent,
            locale='ko-KR',
            timezone_id='Asia/Seoul',
        )
        
        await context.set_extra_http_headers({
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        
        page = await context.new_page()
        
        # 자동화 감지 우회
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}};
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko']});
        """)
        
        try:
            print(f"\n{'='*80}")
            print(f"매물 크롤링 시작 (v3)")
            print(f"{'='*80}")
            print(f"URL: {url}\n")
            
            # 매물 ID 추출
            article_id = 'unknown'
            id_match = re.search(r'/articles/(\d+)', url)
            if id_match:
                article_id = id_match.group(1)
            
            # 데이터 구조 초기화 (columns_structure.json 기준)
            result = {
                '메타정보': {
                    '매물ID': article_id,
                    'URL': url,
                    '수집시간': datetime.now().isoformat(),
                    'User-Agent': user_agent
                },
                '매물정보': {},
                '대출정보': {
                    '대출한도': {},
                    '금리정보': []
                },
                '매물분포': {},
                '실거래가': {
                    '매매': [],
                    '전세': [],
                    '월세': []
                },
                '대출계산기': {},
                '기본정보': {
                    '이미지': []
                },
                '단지정보': {},
                '개발예정': [],
                '시설정보': {},
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
            
            # 2. 스크롤
            print("2. 콘텐츠 로딩...")
            await human_like_scroll(page)
            print("   ✓ 완료\n")

            # 3. 동적 크롤링 1단계: 소개말 더보기
            print("3. 소개말 더보기 클릭...")
            intro_clicked = await click_button_with_text(page, ['소개말 더보기', '소개말더보기'], "소개말 더보기")
            if intro_clicked:
                await random_sleep(1, 2)  # 소개말 로딩 대기
            print()
            
            # 4. 동적 크롤링 2단계: 관리비 상세보기
            print("4. 관리비 상세보기 클릭...")
            mgmt_clicked = await click_button_with_text(page, ['관리비', '상세보기'], "관리비 상세보기")
            
            # 관리비 상세 데이터 수집
            mgmt_detail_text = ""
            if mgmt_clicked:
                await random_sleep(1, 1.5)
                # 관리비 상세 데이터 수집
                mgmt_detail_text = await page.evaluate("() => document.body.innerText")
                print("     ✓ 관리비 상세 데이터 수집 완료")
                
                # 닫기 버튼 클릭
                close_clicked = await click_button_with_text(page, ['닫기', '닫기'], "관리비 닫기")
                if not close_clicked:
                    # ESC 키로 닫기 시도
                    await page.keyboard.press('Escape')
                    await random_sleep(0.5, 1)
                    print("     ✓ ESC로 닫기 완료")
            print()
            
            # 5. 페이지 텍스트 수집 (소개말 더보기 클릭 후)
            print("5. 기본 데이터 추출...")
            page_text = await page.evaluate("() => document.body.innerText")
            
            # === 매물정보 추출 ===
            # 기본정보에서 이미 수집된 데이터 활용
            if '공급면적_제곱미터' in result['기본정보']:
                result['매물정보']['공급면적_제곱미터'] = result['기본정보']['공급면적_제곱미터']
            if '전용면적_제곱미터' in result['기본정보']:
                result['매물정보']['전용면적_제곱미터'] = result['기본정보']['전용면적_제곱미터']
            if '해당층' in result['기본정보']:
                result['매물정보']['해당층'] = result['기본정보']['해당층']
            if '총층수' in result['기본정보']:
                result['매물정보']['총층수'] = result['기본정보']['총층수']
            if '향' in result['기본정보']:
                result['매물정보']['향'] = result['기본정보']['향']
            
            # 집주인확인매물
            if '집주인확인매물' in page_text:
                result['매물정보']['집주인확인매물'] = True
                owner_match = re.search(r'집주인확인매물\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', page_text)
                if owner_match:
                    result['매물정보']['집주인확인일'] = f"{owner_match.group(1)}-{owner_match.group(2).zfill(2)}-{owner_match.group(3).zfill(2)}"
            
            # === 대출정보 추출 ===
            # 대출한도
            ltv_match = re.search(r'(투기과열|조정대상|비규제)[,\s]*LTV\s*(\d+)%', page_text)
            if ltv_match:
                result['대출정보']['대출한도']['규제지역'] = ltv_match.group(1)
                result['대출정보']['대출한도']['LTV_퍼센트'] = int(ltv_match.group(2))
            
            loan_amount_match = re.search(r'최대\s+([\d억,\s]+만?원)', page_text)
            if loan_amount_match:
                result['대출정보']['대출한도']['최대금액'] = loan_amount_match.group(1).strip()
            
            # 금리정보
            bank_pattern = re.compile(r'([가-힣A-Z]+(?:은행|생명|저축은행))\s*([\d.]+%~[\d.]+%|[\d.]+%)')
            for match in bank_pattern.finditer(page_text):
                result['대출정보']['금리정보'].append({
                    '은행명': match.group(1),
                    '금리범위': match.group(2)
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
            
            # === 기본정보 추출 ===
            # 매매가
            sale_price_match = re.search(r'매매가\s*([\d억,\s]+만?원)', page_text)
            if sale_price_match:
                result['기본정보']['매매가'] = sale_price_match.group(1).strip()
            
            # 관리비부과기준
            mgmt_basis_match = re.search(r'관리비부과기준\s*([^\n]+)', page_text)
            if mgmt_basis_match:
                result['기본정보']['관리비부과기준'] = mgmt_basis_match.group(1).strip()
            
            # 관리비 (기본)
            mgmt_fee_match = re.search(r'관리비\s*(\d+)만원', page_text)
            if mgmt_fee_match:
                result['기본정보']['관리비_만원'] = int(mgmt_fee_match.group(1))
            
            # 관리비 상세 (상세보기 클릭 후)
            mgmt_detail_match = re.search(r'관리비 합계\s*([\d,]+)원', page_text)
            if mgmt_detail_match:
                result['기본정보']['관리비합계_원'] = int(mgmt_detail_match.group(1).replace(',', ''))
            
            # 포함 항목
            include_match = re.search(r'포함 항목\(사용료\)\s*:\s*([^\n]+)', page_text)
            if include_match:
                result['기본정보']['관리비포함항목'] = include_match.group(1).strip()
            
            # 관리비 기준
            mgmt_standard_match = re.search(r'관리비 기준\s*:\s*([^\n]+)', page_text)
            if mgmt_standard_match:
                result['기본정보']['관리비기준'] = mgmt_standard_match.group(1).strip()
            
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
            
            # 매물소개 (소개말 더보기 클릭 후 전체 내용)
            intro_match = re.search(r'매물소개\s*\n((?:(?!최초게재|허위|단지 정보|로딩중).)+)', page_text, re.DOTALL)
            if intro_match:
                intro_text = intro_match.group(1).strip()
                # 불필요한 부분 제거
                intro_text = re.sub(r'\d+ 번째.*', '', intro_text)
                intro_text = re.sub(r'선택됨.*', '', intro_text)
                intro_lines = [line.strip() for line in intro_text.split('\n') if line.strip() and len(line.strip()) > 5]
                result['기본정보']['매물소개'] = '\n'.join(intro_lines)
            
            # 최초게재일
            first_post_match = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*최초게재([가-힣]+)\s*제공', page_text)
            if first_post_match:
                result['기본정보']['최초게재일'] = f"{first_post_match.group(1)}-{first_post_match.group(2).zfill(2)}-{first_post_match.group(3).zfill(2)}"
                result['기본정보']['제공업체'] = first_post_match.group(4)
            
            # === 시설정보 추출 ===
            # 기본 시설 목록
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
            
            # 기본 시설 체크
            for facility_key, keywords in facilities.items():
                for keyword in keywords:
                    if keyword in page_text:
                        result['시설정보'][facility_key] = True
                        break
                else:
                    result['시설정보'][facility_key] = False
            
            # 추가 시설 자동 감지 (옵션/시설 섹션에서)
            # "옵션" 또는 "시설" 키워드 근처의 텍스트에서 추가 항목 찾기
            option_patterns = [
                r'옵션[^\n]*?([가-힣]+(?:장|기|대|기기|시설))',
                r'시설[^\n]*?([가-힣]+(?:장|기|대|기기|시설))',
                r'포함[^\n]*?([가-힣]+(?:장|기|대|기기|시설))'
            ]
            
            additional_facilities = set()
            for pattern in option_patterns:
                matches = re.finditer(pattern, page_text)
                for match in matches:
                    facility_name = match.group(1).strip()
                    # 이미 있는 시설이 아니고, 2글자 이상인 경우만
                    if facility_name not in facilities and len(facility_name) >= 2:
                        additional_facilities.add(facility_name)
            
            # 추가 시설을 시설정보에 추가
            for facility in additional_facilities:
                if facility in page_text:
                    result['시설정보'][facility] = True
            
            print("   ✓ 완료\n")
            
            # 6. 이미지 수집
            print("6. 이미지 수집...")
            result['기본정보']['이미지'] = await save_images(page, article_id)
            print()

            # === 단지정보 추출 ===
            print("7. 단지정보 추출...")
            
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
                        print(f"     → {selector} 버튼 {len(buttons)}개 발견")
                        
                        for btn in buttons:
                            try:
                                # 버튼이 보이는지 확인
                                is_visible = await btn.is_visible()
                                if not is_visible:
                                    continue
                                
                                # 버튼 크기 확인 (40x40)
                                box = await btn.bounding_box()
                                if box:
                                    print(f"     → 버튼 크기: {int(box['width'])}x{int(box['height'])}")
                                    
                                    # 40x40 근처 크기의 버튼 찾기
                                    if 35 <= box['width'] <= 50 and 35 <= box['height'] <= 50:
                                        print(f"     ✓ 로드뷰 버튼 발견!")
                                        
                                        # 버튼 위치로 스크롤
                                        await page.evaluate(f"window.scrollTo(0, {box['y'] - 200})")
                                        await random_sleep(0.5, 1)
                                        
                                        # 새 창 열림 감지
                                        try:
                                            async with page.expect_popup(timeout=5000) as popup_info:
                                                await btn.click()
                                                await random_sleep(1, 2)
                                            
                                            # 새 창에서 URL 가져오기
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
                                                
                                                # 좌표 유효성 검증
                                                if 33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0:
                                                    result['단지정보']['위도'] = lat
                                                    result['단지정보']['경도'] = lng
                                                    print(f"     ✓ 좌표 수집 완료: {lat}, {lng}")
                                                    coord_found = True
                                                    
                                                    # 로드뷰 페이지 닫기
                                                    await roadview_page.close()
                                                    break
                                            
                                            # 로드뷰 페이지 닫기
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
                    
                    # 다양한 패턴으로 검색
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
                                
                                # 좌표 유효성 검증
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
                    print("     ℹ 좌표 정보를 찾을 수 없음")
                
                # 원래 페이지로 돌아가기
                print("     → 원래 페이지로 복귀...")
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await random_sleep(1, 2)
                    
            except Exception as e:
                print(f"     ℹ 좌표 추출 실패: {e}")
                import traceback
                traceback.print_exc()
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
            
            # === 개발예정 추출 ===
            print("8. 개발예정 추출...")
            
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
            
            # === 중개사 추출 ===
            print("9. 중개사 정보 추출...")
            
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
            
            # === 중개보수 추출 ===
            print("10. 중개보수 추출...")
            
            brokerage_match = re.search(r'중개 보수\s*최대\s*([\d,]+)만원', page_text)
            if brokerage_match:
                result['중개보수']['최대금액_원'] = int(brokerage_match.group(1).replace(',', '')) * 10000
            
            rate_match = re.search(r'상한 요율\s*([\d.]+)%', page_text)
            if rate_match:
                result['중개보수']['상한요율_퍼센트'] = float(rate_match.group(1))
            
            print("   ✓ 완료\n")
            
            # === 세금 추출 ===
            print("11. 세금 정보 추출...")
            
            acquisition_match = re.search(r'취득세 합계\s*약\s*([\d,]+)만원', page_text)
            if acquisition_match:
                result['세금']['취득세_원'] = int(acquisition_match.group(1).replace(',', '')) * 10000
            
            property_match = re.search(r'재산세 합계\s*약\s*([\d,]+)만원', page_text)
            if property_match:
                result['세금']['재산세_원'] = int(property_match.group(1).replace(',', '')) * 10000
            
            if '종합부동산세' in page_text and '과세대상 아님' in page_text:
                result['세금']['종합부동산세'] = '과세대상 아님'
            
            print("   ✓ 완료\n")
            
            # === 관리비 추출 ===
            print("12. 관리비 상세 추출...")
            
            # 관리비 상세보기에서 수집한 데이터 사용
            mgmt_source = mgmt_detail_text if mgmt_detail_text else page_text
            
            # 기본 관리비 정보 (기본정보에서 가져오기)
            if '관리비_만원' in result['기본정보']:
                result['관리비']['관리비_만원'] = result['기본정보']['관리비_만원']
            
            # 관리비 상세 정보 (더 유연한 패턴)
            recent_mgmt_match = re.search(r'(\d{4})[.\s]*(\d{1,2})[.\s]*([\d,]+)\s*원', mgmt_source)
            if recent_mgmt_match:
                result['관리비']['기준년월'] = f"{recent_mgmt_match.group(1)}-{recent_mgmt_match.group(2).zfill(2)}"
                result['관리비']['최근관리비_원'] = int(recent_mgmt_match.group(3).replace(',', ''))
            
            avg_match = re.search(r'월\s*평균[:\s]*([\d,]+)\s*원', mgmt_source)
            if avg_match:
                result['관리비']['월평균_원'] = int(avg_match.group(1).replace(',', ''))
            
            summer_match = re.search(r'여름[^\d]*([\d,]+)\s*원', mgmt_source)
            if summer_match:
                result['관리비']['여름평균_원'] = int(summer_match.group(1).replace(',', ''))
            
            winter_match = re.search(r'겨울[^\d]*([\d,]+)\s*원', mgmt_source)
            if winter_match:
                result['관리비']['겨울평균_원'] = int(winter_match.group(1).replace(',', ''))
            
            print("   ✓ 완료\n")
            
            # === 주변대중교통 추출 ===
            print("13. 주변대중교통 추출...")
            
            result['주변대중교통']['버스'] = {}
            
            # 마을버스
            bus_match = re.search(r'버스\s*마을\s*([^\n]+)', page_text)
            if bus_match:
                buses = [b.strip() for b in re.split(r'[,\s]+', bus_match.group(1)) if b.strip() and not b.strip() in ['지선', '간선']]
                if buses:
                    result['주변대중교통']['버스']['마을'] = buses
            
            # 지선
            jiseon_match = re.search(r'지선\s*([\d,\s]+)', page_text)
            if jiseon_match:
                buses = [b.strip() for b in re.split(r'[,\s]+', jiseon_match.group(1)) if b.strip() and b.strip().isdigit()]
                if buses:
                    result['주변대중교통']['버스']['지선'] = buses
            
            # 간선
            ganseon_match = re.search(r'간선\s*([\d,\s]+)', page_text)
            if ganseon_match:
                buses = [b.strip() for b in re.split(r'[,\s]+', ganseon_match.group(1)) if b.strip() and b.strip().isdigit()]
                if buses:
                    result['주변대중교통']['버스']['간선'] = buses
            
            print("   ✓ 완료\n")

            # === 실거래가 동적 크롤링 ===
            print("14. 실거래가 수집 (동적 크롤링)...")
            print(f"{'-'*80}")
            
            # 14-1. 실거래가 더보기
            print("  [1] 실거래가 더보기 클릭...")
            await click_button_with_text(page, ['실거래가', '더보기'], "실거래가 더보기")
            
            # 14-2. 실거래가 상세보기
            print("  [2] 실거래가 상세보기 클릭...")
            detail_clicked = await click_button_with_text(page, ['실거래가', '상세보기'], "실거래가 상세보기")
            
            if detail_clicked:
                await random_sleep(2, 3)
            
            # 14-3. 매매/전세/월세 탭 크롤링
            trade_types = [
                ('매매', '매매'),
                ('전세', '전세'),
                ('월세', '월세')
            ]
            
            for idx, (tab_name, result_key) in enumerate(trade_types, 1):
                print(f"  [{idx+2}] {tab_name} 탭 크롤링...")
                
                try:
                    # 탭 클릭 (첫 번째 탭은 이미 선택되어 있을 수 있음)
                    if idx > 1:  # 매매 탭이 아닌 경우만 클릭
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
                                    break
                            except:
                                continue
                        
                        if not tab_found:
                            print(f"     ℹ {tab_name} 탭 없음")
                            continue
                    else:
                        # 매매 탭은 기본 선택되어 있음
                        await random_sleep(1, 1.5)
                    
                    # 데이터 추출
                    await random_sleep(1, 1.5)
                    trade_page_text = await page.evaluate("() => document.body.innerText")
                    
                    transactions = []
                    # 더 유연한 패턴들
                    patterns = [
                        re.compile(r'(\d{1,2})[./](\d{1,2})[./]\s*(?:[\d.]+\s*)?(\d+)\s*층\s*([^\n]*?)([\d억,\s/]+)'),
                        re.compile(r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})\s*(\d+)\s*층\s*([^\n]*?)([\d억,\s/]+)'),
                        re.compile(r'(\d{1,2})[./](\d{1,2})\s+(\d+)층\s+([\d억,\s/]+)'),
                    ]
                    
                    for pattern in patterns:
                        for match in pattern.finditer(trade_page_text):
                            try:
                                if len(match.groups()) >= 5:  # 전체 패턴
                                    month = match.group(1) if len(match.group(1)) <= 2 else match.group(2)
                                    day = match.group(2) if len(match.group(1)) <= 2 else match.group(3)
                                    floor = int(match.group(3) if len(match.group(1)) <= 2 else match.group(4))
                                    note = match.group(4) if len(match.group(1)) <= 2 else match.group(5)
                                    price = match.group(5) if len(match.group(1)) <= 2 else match.group(6)
                                else:  # 간단한 패턴
                                    month = match.group(1)
                                    day = match.group(2)
                                    floor = int(match.group(3))
                                    note = ""
                                    price = match.group(4)
                                
                                month = month.zfill(2)
                                day = day.zfill(2)
                                price = price.strip()
                                price = re.sub(r'\n.*', '', price)
                                note = note.strip() if note else ""
                                
                                trans = {
                                    '계약일': f"2025-{month}-{day}",
                                    '층': floor,
                                    '가격': price,
                                    '비고': note
                                }
                                transactions.append(trans)
                            except:
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
                    
                    # 샘플 출력
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
            print(f"매매 실거래: {len(result['실거래가']['매매'])}건")
            print(f"전세 실거래: {len(result['실거래가']['전세'])}건")
            print(f"월세 실거래: {len(result['실거래가']['월세'])}건")
            print(f"이미지: {len(result['기본정보']['이미지'])}개")
            print(f"금리정보: {len(result['대출정보']['금리정보'])}개")
            print(f"개발예정: {len(result['개발예정'])}개")
            print(f"{'='*80}\n")
            
            return result
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        finally:
            wait_time = 1  # 대기 시간 단축
            print(f"브라우저를 {wait_time}초 후 종료합니다...")
            await asyncio.sleep(wait_time)
            await browser.close()

async def main():
    """메인 함수"""
    
    print("\n" + "="*80)
    print("네이버 부동산 매물 크롤러 v3")
    print("크롤링방법.txt 기반 완전 재구성 버전")
    print("="*80)
    print("\n[기능]")
    print("  ✓ 컬럼 구조 재정리 (columns_structure.json 기준)")
    print("  ✓ 동적 크롤링 순서 명확화")
    print("  ✓ 이미지 수집 기능")
    print("  ✓ 시설정보 자동 감지")
    print("  ✓ 관리비 상세보기 동적 크롤링")
    print("  ✓ 실거래가 상세보기 → 매매/전세/월세 탭 크롤링")
    print("  ✓ 크롤링 방지 우회 (랜덤 User-Agent, 타임슬립, 사람처럼 스크롤)")
    print("="*80)
    print()
    
    # 1. URL 데이터 파일 경로 입력
    url_file_path = input("URL 데이터 파일 경로를 입력하세요: ").strip()
    
    # 파일 존재 확인
    if not os.path.exists(url_file_path):
        print(f"❌ 파일을 찾을 수 없습니다: {url_file_path}")
        return
    
    # 2. 저장 경로 입력
    save_dir = input("결과 저장 경로를 입력하세요: ").strip()
    
    # 저장 폴더 생성
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        print(f"✓ 저장 폴더 생성: {save_dir}")
    
    # 3. URL 데이터 파일 읽기
    try:
        with open(url_file_path, 'r', encoding='utf-8') as f:
            url_data = json.load(f)
        
        url_list = url_data.get('URL목록', [])
        total_urls = len(url_list)
        
        if total_urls == 0:
            print("❌ URL목록이 비어있습니다.")
            return
        
        print(f"\n✓ URL 데이터 로드 완료")
        print(f"  - 총 URL 수: {total_urls}개")
        print(f"  - 크롤링 대상: 상위 3개")
        print()
        
    except Exception as e:
        print(f"❌ URL 데이터 파일 읽기 실패: {e}")
        return
    
    # 4. 상위 3개 URL 크롤링
    target_urls = url_list[:3]
    success_count = 0
    fail_count = 0
    
    for idx, url_info in enumerate(target_urls, 1):
        url = url_info.get('URL', '')
        article_id = url_info.get('매물ID', 'unknown')
        
        print(f"\n{'='*80}")
        print(f"[{idx}/3] 매물 크롤링 시작")
        print(f"매물ID: {article_id}")
        print(f"URL: {url}")
        print(f"{'='*80}\n")
        
        try:
            # 크롤링 실행
            result = await crawl_article(url)
            
            if result:
                # 파일 저장
                filename = f'article_v3_{article_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                filepath = os.path.join(save_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                print(f"\n✅ [{idx}/3] 크롤링 성공!")
                print(f"   저장 위치: {filepath}")
                success_count += 1
            else:
                print(f"\n❌ [{idx}/3] 크롤링 실패")
                fail_count += 1
        
        except Exception as e:
            print(f"\n❌ [{idx}/3] 크롤링 중 오류 발생: {e}")
            fail_count += 1
        
        # 다음 크롤링 전 대기 (마지막 URL이 아닌 경우)
        if idx < len(target_urls):
            wait_time = random.uniform(1, 2.5)
            print(f"\n⏳ 다음 크롤링까지 {wait_time:.1f}초 대기...\n")
            await asyncio.sleep(wait_time)
    
    # 5. 최종 결과 출력
    print(f"\n{'='*80}")
    print("전체 크롤링 완료")
    print(f"{'='*80}")
    print(f"성공: {success_count}개")
    print(f"실패: {fail_count}개")
    print(f"저장 위치: {save_dir}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(main())
