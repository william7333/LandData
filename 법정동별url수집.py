"""
법정동별 매물 URL 수집기
- 사용자 입력으로 URL과 저장 경로 지정
- 지역의 모든 단지를 자동으로 순회
- 각 단지의 매물 URL 자동 수집
- Playwright 기반
"""
import asyncio
import json
import random
from playwright.async_api import async_playwright
from datetime import datetime
import re
import os

# User-Agent 목록
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

async def random_sleep(min_sec=1, max_sec=3):
    """랜덤 대기"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def collect_complex_urls(page):
    """단지 URL 수집"""
    
    print("\n1. 단지 목록 로딩...")
    
    # 스크롤하여 모든 단지 로드
    print("   → 스크롤하여 모든 단지 로드 중...")
    
    last_height = await page.evaluate("() => document.body.scrollHeight")
    scroll_attempts = 0
    max_attempts = 20
    
    while scroll_attempts < max_attempts:
        # 스크롤
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await random_sleep(1.5, 2.5)
        
        # "더보기" 버튼 찾아서 클릭
        try:
            more_buttons = await page.query_selector_all('button:has-text("더보기"), button:has-text("더 보기"), a:has-text("더보기")')
            for btn in more_buttons:
                is_visible = await btn.is_visible()
                if is_visible:
                    await btn.click()
                    print(f"   → 더보기 버튼 클릭")
                    await random_sleep(2, 3)
                    break
        except:
            pass
        
        # 새 높이 확인
        new_height = await page.evaluate("() => document.body.scrollHeight")
        
        if new_height == last_height:
            break
        
        last_height = new_height
        scroll_attempts += 1
        
        if scroll_attempts % 5 == 0:
            print(f"   → 스크롤 진행 중... ({scroll_attempts}/{max_attempts})")
    
    print("   ✓ 스크롤 완료\n")
    
    # 단지 링크 수집
    print("   → 단지 링크 수집 중...")
    
    complex_links = await page.evaluate("""
        () => {
            const links = [];
            const allLinks = document.querySelectorAll('a');
            
            allLinks.forEach((el, index) => {
                const href = el.href || el.getAttribute('href') || '';
                
                // complexes가 포함된 링크만
                if (/complexes\\/\\d+/.test(href)) {
                    const text = (el.innerText || el.textContent || '').trim();
                    
                    // 중복 제거를 위해 complex ID 추출
                    const match = href.match(/complexes\\/(\\d+)/);
                    if (match) {
                        links.push({
                            index: index,
                            complexId: match[1],
                            href: href,
                            text: text.substring(0, 80).replace(/\\n/g, ' ').trim(),
                            isVisible: el.offsetParent !== null
                        });
                    }
                }
            });
            
            return links;
        }
    """)
    
    # 중복 제거 (같은 complex ID)
    unique_complexes = {}
    for link in complex_links:
        complex_id = link['complexId']
        if complex_id not in unique_complexes:
            unique_complexes[complex_id] = link
    
    complex_list = list(unique_complexes.values())
    
    print(f"   ✓ {len(complex_list)}개 단지 발견\n")
    
    return complex_list

async def collect_articles_from_complex(page, complex_url, complex_name, is_first_complex=False, article_button_selector=None):
    """단지에서 매물 URL 수집"""
    
    try:
        # 단지 페이지로 이동 (자동으로 tab=transaction으로 이동됨)
        print(f"      → 단지 페이지 이동...")
        
        await page.goto(complex_url, wait_until='domcontentloaded', timeout=60000)
        await random_sleep(2, 3)
        await page.wait_for_load_state('networkidle', timeout=30000)
        
        current_url = page.url
        print(f"      ✓ 페이지 로드 완료")
        print(f"         URL: {current_url[:80]}...")
        
        # 매물 탭으로 이동 - URL 변경
        print(f"      → 매물 탭 URL로 변경 중...")
        
        # URL 변경 규칙: tab=transaction → tab=article
        article_url = current_url.replace('tab=transaction', 'tab=article')
        
        # articleTradeTypes 파라미터가 있으면 제거
        if 'articleTradeTypes=' in article_url:
            # articleTradeTypes 파라미터 제거
            import re
            article_url = re.sub(r'&articleTradeTypes=[^&]*', '', article_url)
        
        print(f"      → 변경된 URL: {article_url[:80]}...")
        
        # 새 URL로 이동
        await page.goto(article_url, wait_until='domcontentloaded', timeout=60000)
        await random_sleep(2, 3)
        await page.wait_for_load_state('networkidle', timeout=30000)
        
        final_url = page.url
        print(f"      ✓ 매물 탭 이동 완료: {final_url[:80]}...\n")
        
        # 3단계: 실제 단지명 추출
        print(f"      → 3단계: 실제 단지명 추출...")
        
        real_complex_name = await page.evaluate("""
            () => {
                // 여러 선택자로 단지명 찾기
                const selectors = [
                    'h1',
                    'h2',
                    '.complex_name',
                    '[class*="complex"]',
                    '[class*="title"]'
                ];
                
                for (let selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    for (let el of elements) {
                        const text = (el.innerText || el.textContent || '').trim();
                        // "단지" 또는 "아파트"가 포함되고, 너무 길지 않은 텍스트
                        if ((text.includes('단지') || text.includes('아파트') || text.includes('빌라')) && 
                            text.length < 50 && text.length > 3) {
                            // 불필요한 텍스트 제거
                            const cleaned = text.split('\\n')[0].trim();
                            if (cleaned.length > 3 && cleaned.length < 50) {
                                return cleaned;
                            }
                        }
                    }
                }
                
                // 못 찾으면 페이지 상단의 첫 번째 큰 텍스트
                const allText = document.body.innerText;
                const lines = allText.split('\\n');
                for (let line of lines.slice(0, 10)) {
                    const trimmed = line.trim();
                    if ((trimmed.includes('단지') || trimmed.includes('아파트')) && 
                        trimmed.length < 50 && trimmed.length > 3) {
                        return trimmed;
                    }
                }
                
                return null;
            }
        """)
        
        if real_complex_name:
            complex_name = real_complex_name
            print(f"      ✓ 실제 단지명: {complex_name}")
        else:
            print(f"      ℹ 단지명 추출 실패, 기존 이름 사용: {complex_name}")
        
        # "매물목록 펼치기" 버튼 클릭
        print(f"      → 매물목록 펼치기 버튼 찾는 중...")
        
        expand_buttons = await page.query_selector_all('button.ArticleCard_button-expand__Tpi_1, button:has-text("매물목록 펼치기"), button:has-text("펼치기")')
        
        if expand_buttons:
            print(f"      ✓ {len(expand_buttons)}개 펼치기 버튼 발견")
            
            for idx, btn in enumerate(expand_buttons, 1):
                try:
                    is_visible = await btn.is_visible()
                    if not is_visible:
                        continue
                    
                    await btn.scroll_into_view_if_needed()
                    await random_sleep(0.3, 0.6)
                    await btn.click()
                    await random_sleep(1, 2)
                    
                except Exception as e:
                    continue
            
            print(f"      ✓ 모든 펼치기 버튼 클릭 완료")
            await random_sleep(2, 3)
        
        # 매물 URL 수집
        print(f"      → 매물 URL 수집 중...")
        
        all_article_links = await page.evaluate("""
            () => {
                const links = [];
                const allLinks = document.querySelectorAll('a');
                
                allLinks.forEach((el, index) => {
                    const href = el.href || el.getAttribute('href') || '';
                    
                    if (/articles\\/\\d+/.test(href)) {
                        const text = (el.innerText || el.textContent || '').trim();
                        
                        links.push({
                            href: href,
                            text: text.substring(0, 80).replace(/\\n/g, ' ').trim(),
                        });
                    }
                });
                
                return links;
            }
        """)
        
        # 매물 ID 추출 및 중복 제거
        property_urls = []
        visited_ids = set()
        
        for link in all_article_links:
            id_match = re.search(r'articles/(\d+)', link['href'])
            if id_match:
                article_id = id_match.group(1)
                
                if article_id not in visited_ids:
                    visited_ids.add(article_id)
                    property_urls.append({
                        '매물ID': article_id,
                        'URL': f"https://fin.land.naver.com/articles/{article_id}",
                        '매물정보': link['text'][:50] if link['text'] else ''
                    })
        
        print(f"      ✓ {len(property_urls)}개 매물 URL 수집 완료")
        
        # 매물 URL 리스트와 실제 단지명을 함께 반환
        return (property_urls, complex_name)
        
    except Exception as e:
        print(f"      ❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return ([], complex_name) if not is_first_complex else ('CLICK_INFO', None)

async def collect_all_properties(start_url, save_base_folder):
    """모든 단지의 매물 URL 수집"""
    
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
            viewport={'width': 1920, 'height': 1080},
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
            print(f"네이버 부동산 매물 URL 수집 시작 (v3 - 전체 단지 자동 순회)")
            print(f"{'='*80}")
            print(f"시작 URL: {start_url}")
            print(f"저장 경로: {save_base_folder}\n")
            
            # 1. 시작 페이지 로드
            print("0. 시작 페이지 로딩...")
            await page.goto(start_url, wait_until='domcontentloaded', timeout=60000)
            await random_sleep(2, 4)
            await page.wait_for_load_state('networkidle', timeout=30000)
            print("   ✓ 페이지 로딩 완료\n")
            
            # 2. 단지 목록 수집
            complex_list = await collect_complex_urls(page)
            
            if not complex_list:
                print("⚠ 단지를 찾을 수 없습니다")
                await browser.close()
                return None
            
            # 3. 각 단지 순회 (전체)
            print(f"2. 단지 순회 시작 (총 {len(complex_list)}개)\n")
            print(f"{'='*80}\n")
            
            all_results = []
            total_properties = 0
            
            for idx, complex_info in enumerate(complex_list, 1):
                complex_id = complex_info['complexId']
                complex_name = complex_info['text'] or f"단지{complex_id}"
                complex_url = complex_info['href']
                
                print(f"[{idx}/{len(complex_list)}] {complex_name}")
                print(f"   URL: {complex_url}")
                
                # 매물 URL 수집 (모든 단지에서 자동 클릭)
                property_urls = await collect_articles_from_complex(page, complex_url, complex_name, False, None)
                
                if property_urls:
                    # 결과 저장 (collect_articles_from_complex에서 반환된 complex_name 사용)
                    # property_urls는 튜플 (urls, real_name) 형태로 반환됨
                    actual_urls, actual_complex_name = property_urls
                    
                    complex_result = {
                        '단지정보': {
                            '순번': idx,
                            '단지ID': complex_id,
                            '단지명': actual_complex_name,
                            '단지URL': complex_url,
                            '수집시간': datetime.now().isoformat(),
                            '매물수': len(actual_urls)
                        },
                        '매물URL목록': actual_urls
                    }
                    
                    all_results.append(complex_result)
                    total_properties += len(actual_urls)
                    
                    # 개별 단지 파일 저장 (실제 단지명 사용)
                    safe_name = re.sub(r'[\\/:*?"<>|]', '_', actual_complex_name)
                    folder_path = f"{save_base_folder}/{safe_name}"
                    os.makedirs(folder_path, exist_ok=True)
                    
                    filename = f"{folder_path}/property_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(complex_result, f, ensure_ascii=False, indent=2)
                    
                    print(f"   ✓ 저장: {filename}")
                else:
                    print(f"   ℹ 매물 없음")
                
                print()
                
                # 다음 단지로 (과도한 요청 방지)
                await random_sleep(2, 4)
            
            # 4. 전체 결과 저장
            print(f"\n{'='*80}")
            print(f"전체 수집 완료")
            print(f"{'='*80}")
            print(f"전체 단지 수: {len(complex_list)}개")
            print(f"매물 수집 단지: {len(all_results)}개")
            print(f"총 매물 수: {total_properties}개")
            print(f"{'='*80}\n")
            
            # 전체 요약 파일 저장
            summary = {
                '수집정보': {
                    '수집시간': datetime.now().isoformat(),
                    '시작URL': start_url,
                    '총단지수': len(complex_list),
                    '수집단지수': len(all_results),
                    '총매물수': total_properties,
                    '버전': 'v3',
                    '처리방식': 'URL 변경 (tab=transaction → tab=article)'
                },
                '단지목록': all_results
            }
            
            summary_file = f"{save_base_folder}/전체요약_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 전체 요약 저장: {summary_file}\n")
            
            # 브라우저 유지
            print(f"브라우저를 5초 후 종료합니다...")
            await asyncio.sleep(5)
            
            await browser.close()
            
            return summary
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
            await asyncio.sleep(5)
            await browser.close()
            return None

async def main():
    """메인 함수"""
    
    print("\n" + "="*80)
    print("법정동별 매물 URL 수집기")
    print("="*80)
    print("\n[기능]")
    print("  ✓ 지역의 모든 단지 자동 순회")
    print("  ✓ 자동 스크롤 및 '더보기' 클릭")
    print("  ✓ URL 변경으로 매물 탭 이동 (tab=transaction → tab=article)")
    print("  ✓ '매물목록 펼치기' 자동 클릭")
    print("  ✓ 단지별 개별 파일 저장")
    print("  ✓ 전체 요약 파일 생성")
    print()
    
    # 시작 URL 입력 받기
    print("원하는 법정동의 단지별매물이 존재하는 url을 입력하세요:")
    print("예시: https://fin.land.naver.com/regions?si=1100000000&gun=1150000000&eup=1150010500")
    start_url = input("\n입력: ").strip()
    
    if not start_url:
        print("\n❌ URL을 입력하지 않았습니다")
        return
    
    if not start_url.startswith('http'):
        print("\n❌ 올바른 URL 형식이 아닙니다")
        return
    
    print()
    
    # 저장 폴더 입력 받기
    print("url이 저장될 경로를 입력하세요:")
    print("예시: 매물url데이터/서울시/강서구/마곡동")
    save_base_folder = input("\n입력: ").strip()
    
    if not save_base_folder:
        print("\n❌ 저장 경로를 입력하지 않았습니다")
        return
    
    print()
    print("="*80)
    print(f"시작 URL: {start_url}")
    print(f"저장 경로: {save_base_folder}")
    print("="*80)
    print()
    
    result = await collect_all_properties(start_url, save_base_folder)
    
    if result:
        print("\n✅ 전체 수집 성공!")
    else:
        print("\n❌ 수집 실패")

if __name__ == "__main__":
    asyncio.run(main())
