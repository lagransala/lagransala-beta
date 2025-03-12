self: super: {
  crawl4ai = super.buildPythonPackage rec {
    pname = "crawl4ai";
    version = "0.5.0.post4";
    src = super.fetchPypi {
      inherit pname version;
      sha256 = "sha256-BrJTiucALOc7q4TMDpMWS7R23udaCOl4PA+wJ5afO/g=";
    };
    doCheck = false;
    preBuild = ''
      export HOME=$(pwd)
    '';
    nativeBuildInputs = with super; [ setuptools wheel ];
    propagatedBuildInputs = with super; [
      setuptools
      wheel
      aiosqlite
      lxml
      litellm
      numpy
      pillow
      playwright
      python-dotenv
      requests
      beautifulsoup4
      # tf-playwright-stealth #TODO: package
      playwright-stealth
      xxhash
      rank-bm25
      aiofiles
      colorama
      snowballstemmer
      pydantic
      pyopenssl
      psutil
      nltk
      rich
      cssselect
      httpx
      fake-useragent
      click
      pyperclip
      faust-cchardet
      aiohttp
      humanize
      transformers
      tokenizers
      pypdf2
      nltk
      scikit-learn
      selenium
    ];
    postInstall = ''
      $out/bin/crawl4ai-setup
      $out/bin/crawl4ai-doctor
    '';
  };
  python-redis-cache = super.buildPythonPackage rec {
    pname = "python_redis_cache";
    version = "4.0.1";
    src = super.fetchPypi {
      inherit pname version;
      sha256 = "sha256-BWi16qLPTAXI/JYp1JIgOidIcjgPwvsGvUIH+qXjidA=";
    };
    doCheck = false;
    preBuild = ''
      export HOME=$(pwd)
    '';
    nativeBuildInputs = with super; [ wheel ];
  };
}
