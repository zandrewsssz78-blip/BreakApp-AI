all:
	pdflatex -shell-escape main.tex
	biber main
	pdflatex -shell-escape main.tex
	pdflatex -shell-escape main.tex

clean:
	rm -f *.aux *.bbl *.bcf *.blg *.log *.out *.run.xml *.toc *.lot *.lof
