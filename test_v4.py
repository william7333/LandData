"""
네이버 부동산 매물 순차 크롤러 v4
- 매물 ID를 순차적으로 증가시키며 크롤링
- 시/구/동 별로 폴더에 저장
- 이미지는 별도 폴더 구조에 저장
- 테스트: 10개 매물만 크롤링
"""
import asyncio
import json
from playwright.async_api import async_playwright
from datetime import datetime
import re
import random
import os
from pathlib import Path
import shutil

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
    
    # 이미지 저장 폴더 생성
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
                        print(f"     ✓ {saved_count}번째 이미지 발견 ({int(img_box['width'])}x{int(img_box['height'])})")
                    
                    if saved_count >= 10:
                        break
            
            except Exception as e:
                continue
        
        if len(images_data) == 0:
            print("     → 페이지 소스에서 이미지 URL 추출 시도...")
            page_content = await page.content()
            
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
        return images_data

def parse_location(location_text):
    """
    위치 텍스트에서 시/구/동 추출
    예: "서울시 금천구 독산동 1028" -> ("서울시", "금천구", "독산동")
    """
    if not location_text:
        return None, None, None
    
    # 패턴: 시/도 + 구/군 + 동/읍/면
    match = re.search(r'([가-힣]+시)\s+([가-힣]+구|[가-힣]+군)\s+([가-힣]+동|[가-힣]+읍|[가-힣]+면)', location_text)
    if match:
        return match.group(1), match.group(2), match.group(3)
    
    return None, None, None

def create_folder_structure(city, district, dong, base_folder="매물데이터"):
    """
    시/구/동 폴더 구조 생성
    예: 매물데이터/서울시/금천구/독산동/
    """
    if not city or not district or not dong:
        folder_path = Path(f"{base_folder}/미분류")
    else:
        folder_path = Path(f"{base_folder}/{city}/{district}/{dong}")
    
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

async def check_article_exists(page, article_id):
    """매물이 존재하는지 확인"""
    url = f"https://fin.land.naver.com/articles/{article_id}"
    
    try:
        response = await page.goto(url, wait_until='domcontentloaded', timeout=15000)
        await random_sleep(1, 2)
        
        page_text = await page.evaluate("() => document.body.innerText")
        
        if '페이지를 찾을 수 없습니다' in page_text or '존재하지 않는' in page_text:
            return False
        
        if '매물이 삭제' in page_text or '종료된 매물' in page_text:
            return False
        
        return True
    
    except Exception as e:
        return False

async def crawl_article_full(page, article_id):
    """
    전체 매물 정보 크롤링 (test_v3.py 기반)
    """
    url = f"https://fin.land.naver.com/articles/{article_id}"
    
    try:
        print(f"  → 페이지 로딩...")
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await random_sleep(2, 3)
        
        # 데이터 구조 초기화
        result = {
            '메타정보': {
                '매물ID': article_id,
                'URL': url,
                '수집시간': datetime.now().isoformat(),
            },
            '매물정보': {},
            '기본정보': {'이미지': []},
            '단지정보': {},
        }
        
        # 스크롤
        await human_like_scroll(page)
        
        # 소개말 더보기
        await click_button_with_text(page, ['소개말 더보기', '소개말더보기'], "소개말 더보기")
        
        # 페이지 텍스트 수집
        page_text = await page.evaluate("() => document.body.innerText")
        
        # 위치 정보 추출
        location_match = re.search(r'위치\s*([가-힣]+시\s+[가-힣]+구\s+[가-힣]+동\s+[\d-]+)', page_text)
        if location_match:
            result['단지정보']['위치'] = location_match.group(1).strip()
            print(f"  ✓ 위치: {result['단지정보']['위치']}")
        
        # 단지명 추출
        complex_match = re.search(r'([가-힣\s]+(?:아파트|빌라|오피스텔))\s*(\d+동)', page_text)
        if complex_match:
            result['단지정보']['단지명'] = complex_match.group(1).strip()
            result['매물정보']['동'] = complex_match.group(2)
        
        # 매매가 추출
        sale_price_match = re.search(r'매매가\s*([\d억,\s]+만?원)', page_text)
        if sale_price_match:
            result['기본정보']['매매가'] = sale_price_match.group(1).strip()
        
        # 면적/층 정보
        area_floor_match = re.search(r'공급면적\s*([\d.]+)㎡', page_text)
        if area_floor_match:
            result['기본정보']['공급면적_제곱미터'] = float(area_floor_match.group(1))
        
        floor_match = re.search(r'층\s*(\d+)층/\s*총\s*(\d+)층', page_text)
        if floor_match:
            result['기본정보']['해당층'] = int(floor_match.group(1))
            result['기본정보']['총층수'] = int(floor_match.group(2))
        
        return result
    
    except Exception as e:
        print(f"  ❌ 크롤링 실패: {e}")
        return None

async def save_article_data(result, article_id):
    """
    크롤링한 데이터를 주소 기반으로 폴더에 저장
    """
    try:
        # 위치 정보 추출
        location_text = result['단지정보'].get('위치', '')
        city, district, dong = parse_location(location_text)
        
        # 매물 데이터 폴더 생성
        data_folder = create_folder_structure(city, district, dong, "매물데이터")
        
        # JSON 파일 저장
        filename = data_folder / f"article_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 데이터 저장: {data_folder}/article_{article_id}_xxx.json")
        
        return city, district, dong, data_folder
    
    except Exception as e:
        print(f"  ❌ 데이터 저장 실패: {e}")
        return None, None, None, None

async def save_article_images(page, article_id, city, district, dong):
    """
    이미지를 주소 기반 폴더에 저장
    """
    try:
        # 이미지 폴더 생성
        image_base_folder = create_folder_structure(city, district, dong, "매물이미지데이터")
        
        # 이미지 수집
        print(f"  → 이미지 수집 중...")
        images_data = await save_images(page, article_id, str(image_base_folder))
        
        print(f"  ✓ 이미지 저장: {image_base_folder}/images_{article_id}/")
        print(f"  ✓ 이미지 개수: {len(images_data)}개")
        
        return images_data
    
    except Exception as e:
        print(f"  ❌ 이미지 저장 실패: {e}")
        return []

async def crawl_single_article(browser, article_id, semaphore):
    """
    단일 매물 크롤링 (병렬 처리용)
    """
    async with semaphore:
        context = await browser.new_context(
            viewport={'width': random.randint(1366, 1920), 'height': random.randint(768, 1080)},
            user_agent=random.choice(USER_AGENTS),
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
            print(f"매물 ID: {article_id}")
            print(f"{'='*80}")
            
            # 1. 매물 존재 확인
            exists = await check_article_exists(page, article_id)
            
            if not exists:
                print(f"  ℹ 매물 없음 - 스킵")
                await context.close()
                return False
            
            print(f"  ✓ 매물 존재 확인")
            
            # 2. 매물 크롤링
            result = await crawl_article_full(page, article_id)
            
            if not result:
                await context.close()
                return False
            
            # 3. 데이터 저장 (주소 기반 폴더)
            city, district, dong, data_folder = await save_article_data(result, article_id)
            
            if not city:
                await context.close()
                return False
            
            # 4. 이미지 저장 (주소 기반 폴더)
            images_data = await save_article_images(page, article_id, city, district, dong)
            
            # 5. JSON 업데이트 (이미지 정보 추가)
            result['기본정보']['이미지'] = images_data
            filename = data_folder / f"article_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            await context.close()
            return True
        
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            await context.close()
            return False

async def main():
    """메인 함수 - 병렬 크롤링 (5개씩)"""
    
    # 시작 매물 ID
    start_id = 2557265773
    # 크롤링할 개수 (테스트: 12개)
    count = 12
    # 동시 실행 개수
    parallel_count = 3
    
    print("\n" + "="*80)
    print("네이버 부동산 병렬 크롤러 v4")
    print("="*80)
    print(f"시작 ID: {start_id}")
    print(f"크롤링 개수: {count}개")
    print(f"병렬 처리: {parallel_count}개씩")
    print(f"매물 데이터: 매물데이터/ 폴더 (주소별 자동 분류)")
    print(f"이미지 데이터: 매물이미지데이터/ 폴더 (주소별 자동 분류)")
    print("="*80 + "\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        # 세마포어로 동시 실행 개수 제한
        semaphore = asyncio.Semaphore(parallel_count)
        
        success_count = 0
        fail_count = 0
        
        try:
            # 매물 ID 리스트 생성
            article_ids = [start_id + i for i in range(count)]
            
            # 병렬 크롤링 실행
            tasks = [crawl_single_article(browser, article_id, semaphore) for article_id in article_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 집계
            for result in results:
                if isinstance(result, Exception):
                    fail_count += 1
                elif result:
                    success_count += 1
                else:
                    fail_count += 1
            
            # 결과 요약
            print("\n" + "="*80)
            print("크롤링 완료")
            print("="*80)
            print(f"성공: {success_count}개")
            print(f"실패: {fail_count}개")
            print(f"총: {count}개")
            print("="*80 + "\n")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
