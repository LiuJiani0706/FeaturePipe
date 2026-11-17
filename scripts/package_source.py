"""Package source and public examples, excluding credentials and private runs."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from build_skill import public_skill_files


def main():
    root=Path(__file__).resolve().parents[1]
    output=root/'release'/'featurepipe-source.zip';output.parent.mkdir(exist_ok=True)
    roots={'featurepipe','tests','scripts','docs','evaluation','prompt_sets','examples','skills','.github'}
    names={'README.md','pyproject.toml','LICENSE','CONTRIBUTING.md','SECURITY.md','.gitignore','.env.example'}
    skill=root/'skills'/'featurepipe-reporter'
    skill_files={'skills/featurepipe-reporter/'+name for name in public_skill_files(skill)}
    files=[p for p in root.rglob('*') if p.is_file() and
           (p.relative_to(root).parts[0] in roots or p.relative_to(root).as_posix() in names) and
           (p.relative_to(root).parts[0]!='skills' or p.relative_to(root).as_posix() in skill_files) and
           '__pycache__' not in p.parts and p.suffix not in {'.pyc','.zip'} and
           p.name!='.env' and not (p.name.startswith('.env.') and p.name!='.env.example')]
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for file in sorted(files):archive.write(file,'featurepipe/'+file.relative_to(root).as_posix())
    with ZipFile(output) as archive:
        assert not any('/runs/' in name or name.endswith('/.env') for name in archive.namelist())
    print('已打包源代码、中文提示词和评价标准；未包含私有采访、运行结果或密钥：'+str(output))


if __name__=='__main__':main()
