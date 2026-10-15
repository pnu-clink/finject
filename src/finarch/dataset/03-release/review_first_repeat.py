"""Explicit v2 entry point. Import never reads or writes legacy review artifacts."""
main = __import__('finarch.dataset.03-release.response_screen', fromlist=['main']).main

if __name__ == '__main__':
    main()
