"""
법정동별 매물 URL 정리
- 전체요약 JSON 파일에서 매물 URL만 추출
- 중복 제거 및 정렬
"""
import json
import re
from datetime import datetime
import os

def extract_urls_from_summary(input_path):
    """전체요약 파일에서 URL 추출"""
    
    print(f"\n{'='*80}")
    print(f"파일 읽기 중...")
    print(f"{'='*80}")
    print(f"경로: {input_path}\n")
    
    try:
        # 파일 읽기
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✓ 파일 로드 완료\n")
        
        # URL 추출
        print(f"URL 추출 중...\n")
        
        all_urls = set()  # 중복 제거를 위해 set 사용
        
        # 단지목록에서 URL 추출
        if '단지목록' in data:
            for complex_data in data['단지목록']:
                if '매물URL목록' in complex_data:
                    for item in complex_data['매물URL목록']:
                        if 'URL' in item:
                            url = item['URL']
                            # https://fin.land.naver.com/articles/{숫자} 패턴 확인
                            if re.match(r'https://fin\.land\.naver\.com/articles/\d{5,}', url):
                                all_urls.add(url)
        
        # URL 정렬 (숫자 순서대로)
        sorted_urls = sorted(list(all_urls), key=lambda x: int(re.search(r'/articles/(\d+)', x).group(1)))
        
        print(f"{'='*80}")
        print(f"추출 결과")
        print(f"{'='*80}")
        print(f"총 URL 수: {len(sorted_urls)}개\n")
        
        # 샘플 출력
        if sorted_urls:
            print(f"[샘플 URL (처음 10개)]")
            for i, url in enumerate(sorted_urls[:10], 1):
                article_id = re.search(r'/articles/(\d+)', url).group(1)
                print(f"{i:3d}. 매물ID: {article_id} | {url}")
            
            if len(sorted_urls) > 10:
                print(f"... 외 {len(sorted_urls) - 10}개\n")
        
        return sorted_urls
        
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {input_path}")
        return None
    except json.JSONDecodeError:
        print(f"❌ JSON 파일 형식이 올바르지 않습니다")
        return None
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_urls(urls, output_path):
    """URL 목록을 JSON 파일로 저장"""
    
    print(f"\n{'='*80}")
    print(f"파일 저장 중...")
    print(f"{'='*80}")
    print(f"경로: {output_path}\n")
    
    try:
        # 폴더 생성
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # URL 목록 생성
        url_list = []
        for idx, url in enumerate(urls, 1):
            article_id = re.search(r'/articles/(\d+)', url).group(1)
            url_list.append({
                '순번': idx,
                '매물ID': article_id,
                'URL': url
            })
        
        # JSON 데이터 생성
        result = {
            '수집정보': {
                '생성시간': datetime.now().isoformat(),
                '총URL수': len(urls),
                '설명': '법정동별 매물 URL 목록'
            },
            'URL목록': url_list
        }
        
        # 파일 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 저장 완료!\n")
        print(f"{'='*80}")
        print(f"저장 정보")
        print(f"{'='*80}")
        print(f"파일 경로: {output_path}")
        print(f"총 URL 수: {len(urls)}개")
        print(f"{'='*80}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ 저장 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    
    print("\n" + "="*80)
    print("법정동별 매물 URL 모으기")
    print("="*80)
    print("\n[기능]")
    print("  ✓ 전체요약 JSON 파일에서 매물 URL 추출")
    print("  ✓ 중복 제거 및 정렬")
    print("  ✓ 깔끔한 JSON 파일로 저장")
    print()
    
    # 입력 파일 경로 받기
    print("원하는 법정동의 url요약파일 경로를 입력하세요:")
    print("예시: 매물url데이터\\서울시\\강서구\\마곡동\\전체요약_20251118_025817.json")
    input_path = input("\n입력: ").strip()
    
    if not input_path:
        print("\n❌ 경로를 입력하지 않았습니다")
        return
    
    # URL 추출
    urls = extract_urls_from_summary(input_path)
    
    if not urls:
        print("\n❌ URL을 추출할 수 없습니다")
        return
    
    if len(urls) == 0:
        print("\n⚠ 추출된 URL이 없습니다")
        return
    
    # 출력 파일 경로 받기
    print("\n원하는 저장경로와 이름을 입력하세요:")
    print("예시: 매물url데이터\\서울시\\강서구\\마곡동\\마곡동url.json")
    output_path = input("\n입력: ").strip()
    
    if not output_path:
        print("\n❌ 경로를 입력하지 않았습니다")
        return
    
    # 파일 저장
    success = save_urls(urls, output_path)
    
    if success:
        print("✅ 완료!")
    else:
        print("❌ 실패")

if __name__ == "__main__":
    main()
