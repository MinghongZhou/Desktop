$(function(){
	
	//----------------DROPDOWN-----------------\\
	$("li").has(".dropdown").hover(
		function() {
			$(this).find(".dropdown").slideDown();
		},
		function() {
			$(this).find(".dropdown").slideUp();
		}
	);
	
	//---------------THUMBNAILS-------------\\
	$(".thumbs li img").hover(
		function() {
			$(this).animate({
				width:"200px",
				height:"134px"
			}, 500);
		},
		function() {
			$(this).animate({
				width:"150px",
				height:"101px"
			}, 500);
		}
	);
	
	//---------------GALLERY-------------\\
	$(".gallery div").hover(
		function() {
			$(this).find("img").fadeIn();
		},
		function() {
			$(this).find("img").fadeOut();
		}
	);
	
	//---------------TABS-------------\\
	$(".tab-list .tab2 a").click(function(e) {
		e.preventDefault();
	});
});