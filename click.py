"""
클릭 기록기
- 사용자의 모든 클릭을 기록
- Playwright 기반
"""
import asyncio
import json
from playwright.async_api import async_playwright
from datetime import datetime

async def record_clicks(start_url, wait_seconds=10):
    """클릭 기록"""
    
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
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ko-KR',
            timezone_id='Asia/Seoul',
        )
        
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
            print(f"클릭 기록기")
            print(f"{'='*80}")
            print(f"URL: {start_url}\n")
            
            # 페이지 로드
            print("1. 페이지 로딩...")
            await page.goto(start_url, wait_until='domcontentloaded', timeout=60000)
            await asyncio.sleep(2)
            await page.wait_for_load_state('networkidle', timeout=30000)
            print("   ✓ 페이지 로딩 완료\n")
            
            # 클릭 모니터링 시작
            print("2. 클릭 모니터링 시작...")
            
            await page.evaluate("""
                () => {
                    window.allClicks = [];
                    
                    document.addEventListener('click', (e) => {
                        const el = e.target;
                        const text = (el.innerText || el.textContent || '').trim();
                        
                        const clickInfo = {
                            timestamp: new Date().toISOString(),
                            tagName: el.tagName,
                            className: el.className,
                            id: el.id,
                            text: text.substring(0, 100),
                            href: el.href || el.getAttribute('href') || '',
                            role: el.getAttribute('role') || '',
                            dataTab: el.getAttribute('data-tab') || '',
                            type: el.type || '',
                            value: el.value || '',
                            name: el.name || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            title: el.title || ''
                        };
                        
                        window.allClicks.push(clickInfo);
                        console.log('클릭 #' + window.allClicks.length + ':', clickInfo);
                    }, true);
                    
                    console.log('클릭 모니터링 시작됨');
                }
            """)
            
            print("   ✓ 클릭 모니터링 활성화\n")
            
            # 사용자 대기
            print(f"3. 사용자 조작 대기 중...")
            print(f"   → 필요한 버튼들을 클릭해주세요!")
            print(f"   → {wait_seconds}초 후 자동으로 종료됩니다...\n")
            
            # 카운트다운
            for i in range(wait_seconds, 0, -1):
                print(f"   {i}초 남음...")
                await asyncio.sleep(1)
            
            print(f"\n   ✓ 대기 완료!\n")
            
            # 클릭 정보 가져오기
            all_clicks = await page.evaluate("() => window.allClicks || []")
            
            print(f"{'='*80}")
            print(f"클릭 기록 결과")
            print(f"{'='*80}")
            print(f"총 클릭 수: {len(all_clicks)}개\n")
            
            if all_clicks:
                print("[클릭 목록]\n")
                for idx, click in enumerate(all_clicks, 1):
                    print(f"[{idx}번째 클릭]")
                    print(f"  태그: {click['tagName']}")
                    print(f"  클래스: {click['className'][:60]}")
                    print(f"  텍스트: {click['text'][:60]}")
                    if click['id']:
                        print(f"  ID: {click['id']}")
                    if click['role']:
                        print(f"  role: {click['role']}")
                    if click['type']:
                        print(f"  type: {click['type']}")
                    if click['name']:
                        print(f"  name: {click['name']}")
                    if click['ariaLabel']:
                        print(f"  aria-label: {click['ariaLabel']}")
                    if click['href']:
                        print(f"  href: {click['href'][:60]}")
                    print()
                
                # 최종 URL
                final_url = page.url
                print(f"최종 URL: {final_url}\n")
                
                # JSON 저장
                result = {
                    '기록정보': {
                        '기록시간': datetime.now().isoformat(),
                        '시작URL': start_url,
                        '최종URL': final_url,
                        '총클릭수': len(all_clicks),
                        '대기시간_초': wait_seconds
                    },
                    '클릭목록': all_clicks
                }
                
                filename = f'click_record_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                print(f"✅ 저장 완료: {filename}\n")
                
                # Python 코드 생성
                print("="*80)
                print("Python 코드 (복사해서 사용하세요)")
                print("="*80)
                print("\n# 클릭 순서 정의")
                print("click_sequence = [")
                for idx, click in enumerate(all_clicks, 1):
                    print(f"    # {idx}번째 클릭: {click['text'][:30] if click['text'] else click['tagName']}")
                    print("    {")
                    if click['id']:
                        print(f"        'id': '{click['id']}',")
                    if click['className']:
                        classes = click['className'].split()[:2]
                        print(f"        'class': '{' '.join(classes)}',")
                    if click['text']:
                        print(f"        'text': '{click['text'][:30]}',")
                    print(f"        'tag': '{click['tagName'].lower()}',")
                    if click['type']:
                        print(f"        'type': '{click['type']}',")
                    if click['name']:
                        print(f"        'name': '{click['name']}',")
                    print(f"        'desc': '{click['text'][:30] if click['text'] else click['tagName']}'")
                    print("    },")
                print("]\n")
                
            else:
                print("⚠ 클릭이 기록되지 않았습니다\n")
            
            # 브라우저 유지
            print(f"브라우저를 5초 후 종료합니다...")
            await asyncio.sleep(5)
            
            await browser.close()
            
            return all_clicks
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
            await asyncio.sleep(5)
            await browser.close()
            return None

async def main():
    """메인 함수"""
    
    # 시작 URL
    start_url = "https://fin.land.naver.com/complexes/131224?tab=article&transactionPyeongTypeNumber=1&transactionTradeType=A1"
    
    # 대기 시간 (초)
    wait_seconds = 10
    
    print("\n" + "="*80)
    print("클릭 기록기")
    print("="*80)
    print("\n[기능]")
    print("  ✓ 모든 클릭 이벤트 기록")
    print("  ✓ 상세 정보 수집 (태그, 클래스, ID, 텍스트 등)")
    print("  ✓ JSON 파일로 저장")
    print("  ✓ Python 코드 자동 생성")
    print(f"\n⏰ 대기 시간: {wait_seconds}초")
    print()
    
    result = await record_clicks(start_url, wait_seconds)
    
    if result:
        print("\n✅ 클릭 기록 완료!")
    else:
        print("\n❌ 클릭 기록 실패")

if __name__ == "__main__":
    asyncio.run(main())
