"""
Script de verification des corrections backend - Version fichier avec encodage UTF-8.
"""
import os

def main():
    print("=" * 60)
    print("VERIFICATION DES CORRECTIONS BACKEND")
    print("=" * 60)
    print()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Read files directly with UTF-8 encoding
    try:
        with open(os.path.join(base_dir, 'matching', 'services.py'), 'r', encoding='utf-8') as f:
            services_content = f.read()
    except UnicodeDecodeError:
        with open(os.path.join(base_dir, 'matching', 'services.py'), 'r', encoding='latin-1') as f:
            services_content = f.read()
    
    try:
        with open(os.path.join(base_dir, 'matching', 'views_history.py'), 'r', encoding='utf-8') as f:
            history_content = f.read()
    except UnicodeDecodeError:
        with open(os.path.join(base_dir, 'matching', 'views_history.py'), 'r', encoding='latin-1') as f:
            history_content = f.read()
    
    all_checks_passed = True
    
    # Check 1: order_by with date_joined in services.py
    check1 = 'date_joined' in services_content
    status1 = "OK" if check1 else "FAIL"
    print(f"[{status1}] Check 1: order_by avec date_joined")
    if not check1:
        all_checks_passed = False
    
    # Check 2: Exclusion via InteractionHistory
    check2 = 'InteractionHistory' in services_content and 'excluded_ids' in services_content
    status2 = "OK" if check2 else "FAIL"
    print(f"[{status2}] Check 2: Exclusion des profils deja interagis")
    if not check2:
        all_checks_passed = False
    
    # Check 3: matched_only filter in views_history.py
    # Look for Match.ACTIVE pattern
    check3 = ('status=Match.ACTIVE' in history_content or 
              'status=\'active\'' in history_content or
              'status="active"' in history_content)
    status3 = "OK" if check3 else "FAIL"
    print(f"[{status3}] Check 3: Filtre matched_only avec Match.ACTIVE")
    if not check3:
        all_checks_passed = False
    
    # Check 4: order_by in get_my_likes function
    # Find the function boundary
    likes_start = history_content.find('def get_my_likes')
    likes_end = history_content.find('def get_my_passes', likes_start)
    likes_func = history_content[likes_start:likes_end] if likes_start != -1 and likes_end != -1 else ''
    check4 = 'order_by' in likes_func and 'created_at' in likes_func
    status4 = "OK" if check4 else "FAIL"
    print(f"[{status4}] Check 4: order_by(-created_at) dans my-likes")
    if not check4:
        all_checks_passed = False
    
    # Check 5: order_by in get_my_passes function
    passes_start = history_content.find('def get_my_passes')
    passes_end = history_content.find('def revoke_interaction', passes_start)
    passes_func = history_content[passes_start:passes_end] if passes_start != -1 and passes_end != -1 else ''
    check5 = 'order_by' in passes_func and 'created_at' in passes_func
    status5 = "OK" if check5 else "FAIL"
    print(f"[{status5}] Check 5: order_by(-created_at) dans my-passes")
    if not check5:
        all_checks_passed = False
    
    # Check 6: Exclude self from discovery
    check6 = 'user.id' in services_content
    status6 = "OK" if check6 else "WARN"
    print(f"[{status6}] Check 6: Exclusion du profil propre dans discovery")
    
    print()
    print("=" * 60)
    if all_checks_passed:
        print("RESULTAT: TOUTES LES CORRECTIONS SONT IMPLEMENTEES")
    else:
        print("RESULTAT: CERTAINES CORRECTIONS MANQUENT - ACTION REQUISE")
    print("=" * 60)
    
    return 0 if all_checks_passed else 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
