"""
네이버 부동산 페이지 분석 도구
- 페이지의 모든 텍스트 정보 수집
- 클릭 가능한 모든 버튼/링크 분석
- 이미지 정보 수집
- HTML 구조 분석
"""
import asyncio
import json
from playwright.async_api import async_playwright
from datetime import datetime
import re

async def analyze_page(url):
    """페이지 세밀 분석"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
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
            window.chrome = {runtime: {}, loadTimes: function() {}};
        """)
        
        try:
            print(f"\n{'='*80}")
            print(f"페이지 분석 시작")
            print(f"{'='*80}")
            print(f"URL: {url}\n")
            
            result = {
                '분석정보': {
                    'URL': url,
                    '분석시간': datetime.now().isoformat()
                },
                '페이지텍스트': {},
                '버튼목록': [],
                '링크목록': [],
                '이미지목록': [],
                '입력필드목록': [],
                'HTML구조': {}
            }
            
            # 1. 페이지 로드
            print("1. 페이지 로딩...")
            await page.goto(url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)
            print("   ✓ 완료\n")
            
            # 2. 페이지 전체 텍스트 수집
            print("2. 페이지 텍스트 수집...")
            page_text = await page.evaluate("() => document.body.innerText")
            result['페이지텍스트']['전체텍스트'] = page_text
            result['페이지텍스트']['텍스트길이'] = len(page_text)
            print(f"   ✓ {len(page_text)}자 수집\n")
            
            # 3. 모든 버튼 분석
            print("3. 버튼 분석...")
            buttons = await page.query_selector_all('button')
            
            for idx, btn in enumerate(buttons, 1):
                try:
                    is_visible = await btn.is_visible()
                    is_enabled = await btn.is_enabled()
                    text = await btn.inner_text()
                    
                    # 버튼 속성
                    btn_class = await btn.get_attribute('class')
                    btn_id = await btn.get_attribute('id')
                    btn_type = await btn.get_attribute('type')
                    btn_aria_label = await btn.get_attribute('aria-label')
                    
                    # 위치 정보
                    box = await btn.bounding_box()
                    
                    button_info = {
                        '순번': idx,
                        '텍스트': text.strip() if text else '',
                        '보임': is_visible,
                        '활성화': is_enabled,
                        'class': btn_class,
                        'id': btn_id,
                        'type': btn_type,
                        'aria-label': btn_aria_label,
                        '위치': {
                            'x': int(box['x']) if box else None,
                            'y': int(box['y']) if box else None,
                            'width': int(box['width']) if box else None,
                            'height': int(box['height']) if box else None
                        } if box else None
                    }
                    
                    result['버튼목록'].append(button_info)
                    
                except Exception as e:
                    continue
            
            print(f"   ✓ {len(result['버튼목록'])}개 버튼 발견\n")
            
            # 4. 모든 링크 분석
            print("4. 링크 분석...")
            links = await page.query_selector_all('a')
            
            for idx, link in enumerate(links, 1):
                try:
                    is_visible = await link.is_visible()
                    text = await link.inner_text()
                    href = await link.get_attribute('href')
                    
                    link_class = await link.get_attribute('class')
                    link_id = await link.get_attribute('id')
                    
                    box = await link.bounding_box()
                    
                    link_info = {
                        '순번': idx,
                        '텍스트': text.strip() if text else '',
                        'href': href,
                        '보임': is_visible,
                        'class': link_class,
                        'id': link_id,
                        '위치': {
                            'x': int(box['x']) if box else None,
                            'y': int(box['y']) if box else None,
                            'width': int(box['width']) if box else None,
                            'height': int(box['height']) if box else None
                        } if box else None
                    }
                    
                    result['링크목록'].append(link_info)
                    
                except Exception as e:
                    continue
            
            print(f"   ✓ {len(result['링크목록'])}개 링크 발견\n")
            
            # 5. 모든 이미지 분석
            print("5. 이미지 분석...")
            images = await page.query_selector_all('img')
            
            for idx, img in enumerate(images, 1):
                try:
                    is_visible = await img.is_visible()
                    src = await img.get_attribute('src')
                    alt = await img.get_attribute('alt')
                    
                    box = await img.bounding_box()
                    
                    image_info = {
                        '순번': idx,
                        'src': src,
                        'alt': alt,
                        '보임': is_visible,
                        '크기': {
                            'width': int(box['width']) if box else None,
                            'height': int(box['height']) if box else None
                        } if box else None,
                        '위치': {
                            'x': int(box['x']) if box else None,
                            'y': int(box['y']) if box else None
                        } if box else None
                    }
                    
                    result['이미지목록'].append(image_info)
                    
                except Exception as e:
                    continue
            
            print(f"   ✓ {len(result['이미지목록'])}개 이미지 발견\n")
            
            # 6. 입력 필드 분석
            print("6. 입력 필드 분석...")
            inputs = await page.query_selector_all('input, textarea, select')
            
            for idx, inp in enumerate(inputs, 1):
                try:
                    is_visible = await inp.is_visible()
                    inp_type = await inp.get_attribute('type')
                    inp_name = await inp.get_attribute('name')
                    inp_id = await inp.get_attribute('id')
                    inp_placeholder = await inp.get_attribute('placeholder')
                    inp_value = await inp.get_attribute('value')
                    
                    tag_name = await inp.evaluate('(el) => el.tagName')
                    
                    input_info = {
                        '순번': idx,
                        '태그': tag_name.lower(),
                        'type': inp_type,
                        'name': inp_name,
                        'id': inp_id,
                        'placeholder': inp_placeholder,
                        'value': inp_value,
                        '보임': is_visible
                    }
                    
                    result['입력필드목록'].append(input_info)
                    
                except Exception as e:
                    continue
            
            print(f"   ✓ {len(result['입력필드목록'])}개 입력 필드 발견\n")
            
            # 7. HTML 구조 분석
            print("7. HTML 구조 분석...")
            
            # 주요 섹션 찾기
            sections = await page.query_selector_all('section, article, div[class*="section"], div[class*="container"]')
            result['HTML구조']['섹션수'] = len(sections)
            
            # 헤더
            headers = await page.query_selector_all('h1, h2, h3, h4, h5, h6')
            header_texts = []
            for h in headers:
                try:
                    text = await h.inner_text()
                    tag = await h.evaluate('(el) => el.tagName')
                    if text.strip():
                        header_texts.append({
                            '태그': tag.lower(),
                            '텍스트': text.strip()
                        })
                except:
                    continue
            
            result['HTML구조']['헤더목록'] = header_texts
            
            # 테이블
            tables = await page.query_selector_all('table')
            result['HTML구조']['테이블수'] = len(tables)
            
            # 리스트
            lists = await page.query_selector_all('ul, ol')
            result['HTML구조']['리스트수'] = len(lists)
            
            print(f"   ✓ 섹션: {len(sections)}개")
            print(f"   ✓ 헤더: {len(header_texts)}개")
            print(f"   ✓ 테이블: {len(tables)}개")
            print(f"   ✓ 리스트: {len(lists)}개\n")
            
            # 8. 특정 키워드 검색
            print("8. 주요 키워드 검색...")
            keywords = [
                '매매가', '전세', '월세', '관리비', '면적', '층',
                '실거래가', '대출', '금리', '중개사', '단지정보',
                '시설', '교통', '학교', '편의시설', '개발',
                '더보기', '상세보기', '펼치기', '접기', '닫기'
            ]
            
            keyword_results = {}
            for keyword in keywords:
                count = page_text.count(keyword)
                if count > 0:
                    keyword_results[keyword] = count
            
            result['키워드분석'] = keyword_results
            
            for keyword, count in keyword_results.items():
                print(f"   - '{keyword}': {count}회")
            print()
            
            # 9. 클릭 가능한 요소 요약
            print("9. 클릭 가능한 요소 요약...")
            
            clickable_summary = {
                '버튼': {
                    '전체': len(result['버튼목록']),
                    '보이는것': len([b for b in result['버튼목록'] if b['보임']]),
                    '활성화된것': len([b for b in result['버튼목록'] if b['활성화']])
                },
                '링크': {
                    '전체': len(result['링크목록']),
                    '보이는것': len([l for l in result['링크목록'] if l['보임']])
                }
            }
            
            result['클릭가능요소요약'] = clickable_summary
            
            print(f"   ✓ 버튼: 전체 {clickable_summary['버튼']['전체']}개 (보임: {clickable_summary['버튼']['보이는것']}개)")
            print(f"   ✓ 링크: 전체 {clickable_summary['링크']['전체']}개 (보임: {clickable_summary['링크']['보이는것']}개)\n")
            
            # 10. 주요 버튼 텍스트 추출
            print("10. 주요 버튼 텍스트...")
            visible_buttons = [b for b in result['버튼목록'] if b['보임'] and b['텍스트']]
            
            button_texts = {}
            for btn in visible_buttons:
                text = btn['텍스트']
                if text:
                    if text in button_texts:
                        button_texts[text] += 1
                    else:
                        button_texts[text] = 1
            
            result['버튼텍스트통계'] = button_texts
            
            # 상위 20개 출력
            sorted_buttons = sorted(button_texts.items(), key=lambda x: x[1], reverse=True)[:20]
            for text, count in sorted_buttons:
                print(f"   - '{text}': {count}개")
            print()
            
            # 11. 결과 저장
            print("11. 결과 저장...")
            
            # 매물 ID 추출
            article_id = 'unknown'
            id_match = re.search(r'/articles/(\d+)', url)
            if id_match:
                article_id = id_match.group(1)
            
            # JSON 파일로 저장
            filename = f'분석결과_{article_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"   ✓ 저장 완료: {filename}\n")
            
            # 텍스트 파일로도 저장 (읽기 쉽게)
            txt_filename = f'분석결과_{article_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(f"{'='*80}\n")
                f.write(f"네이버 부동산 페이지 분석 결과\n")
                f.write(f"{'='*80}\n\n")
                f.write(f"URL: {url}\n")
                f.write(f"분석시간: {result['분석정보']['분석시간']}\n\n")
                
                f.write(f"{'='*80}\n")
                f.write(f"1. 클릭 가능한 요소 요약\n")
                f.write(f"{'='*80}\n")
                f.write(f"버튼: {clickable_summary['버튼']['전체']}개 (보임: {clickable_summary['버튼']['보이는것']}개, 활성화: {clickable_summary['버튼']['활성화된것']}개)\n")
                f.write(f"링크: {clickable_summary['링크']['전체']}개 (보임: {clickable_summary['링크']['보이는것']}개)\n")
                f.write(f"이미지: {len(result['이미지목록'])}개\n")
                f.write(f"입력필드: {len(result['입력필드목록'])}개\n\n")
                
                f.write(f"{'='*80}\n")
                f.write(f"2. 주요 버튼 목록 (보이는 것만)\n")
                f.write(f"{'='*80}\n")
                for btn in visible_buttons[:30]:
                    f.write(f"[{btn['순번']}] {btn['텍스트']}\n")
                    if btn['class']:
                        f.write(f"    class: {btn['class']}\n")
                    if btn['위치']:
                        f.write(f"    위치: ({btn['위치']['x']}, {btn['위치']['y']}) 크기: {btn['위치']['width']}x{btn['위치']['height']}\n")
                    f.write("\n")
                
                f.write(f"{'='*80}\n")
                f.write(f"3. 키워드 분석\n")
                f.write(f"{'='*80}\n")
                for keyword, count in sorted(keyword_results.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"'{keyword}': {count}회\n")
                f.write("\n")
                
                f.write(f"{'='*80}\n")
                f.write(f"4. 페이지 전체 텍스트 (처음 5000자)\n")
                f.write(f"{'='*80}\n")
                f.write(page_text[:5000])
                f.write("\n...\n")
            
            print(f"   ✓ 텍스트 저장: {txt_filename}\n")
            
            # 최종 요약
            print(f"{'='*80}")
            print("분석 완료")
            print(f"{'='*80}")
            print(f"버튼: {len(result['버튼목록'])}개")
            print(f"링크: {len(result['링크목록'])}개")
            print(f"이미지: {len(result['이미지목록'])}개")
            print(f"입력필드: {len(result['입력필드목록'])}개")
            print(f"페이지 텍스트: {len(page_text)}자")
            print(f"{'='*80}\n")
            
            # 브라우저 유지 (확인용)
            print("브라우저를 10초 후 종료합니다...")
            await asyncio.sleep(10)
            
            await browser.close()
            
            return result
            
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
    print("네이버 부동산 페이지 분석 도구")
    print("="*80)
    print("\n[기능]")
    print("  ✓ 페이지의 모든 텍스트 수집")
    print("  ✓ 클릭 가능한 모든 버튼/링크 분석")
    print("  ✓ 이미지 정보 수집")
    print("  ✓ HTML 구조 분석")
    print("  ✓ 키워드 검색")
    print("  ✓ 결과를 JSON 및 TXT 파일로 저장")
    print("="*80)
    print()
    
    # 기본 URL
    url = "https://fin.land.naver.com/articles/2561970711"
    
    print(f"분석 URL: {url}")
    print()
    
    result = await analyze_page(url)
    
    if result:
        print("\n✅ 분석 성공!")
    else:
        print("\n❌ 분석 실패")

if __name__ == "__main__":
    asyncio.run(main())
